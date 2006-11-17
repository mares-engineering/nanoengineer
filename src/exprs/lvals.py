'''
lvals.py - various kinds of "lvalue" objects (slots for holding attribute values)
with special behavior such as usage-tracking and invalidation/update.

$Id$

===

Ways in which lval classes need to differ from each other:

- how the value they represent is "delivered" (on request of a caller, calling a get_value method or the like):

  - (e.g. as a return value, or as an externally stored value, or as side effects)

  - (e.g. with or without a version-counter)

- how the fact of their value's usage is recorded in the dynamic environment, and what kind of usage is recorded

  - kinds of usage:
    calls of display lists,
    uses of other external objects (qt widgets, opengl state),
    uses of ordinary usage-tracked variables

  (but if dynamic env wants to record usage in order of occurrence, I think it can do that without affecting the track_use API)

- how the decision of what needs recomputing is made

  - e.g. what kinds of inval flags, whether to diff input values before deciding, whether to do partial or incremental recomputes

- with what API the recomputing is accomplished (e.g. call a supplied function, perhaps with certain args)

- how invals of the current value can/should be propogated to previous users of the current value

Other differences, that should *not* be reflected directly in lval classes
(but that might have specific helper functions in this module):

- the specific formula being recomputed (whether expressed a python compute method, an interpreted HL math expr, or a draw method)

- whether some of the storage implied above (eg value caches, usage lists and their subs records, inval flags and their user lists)
  is stored separately from formula instances (to permit sharing of formulas) --
  because if it is, then just make an lval class that calls a different kind of formula (passing it more args when it runs),
  but let the lval class itself be per-storage-instance

- whether the lvalues reside in a single object-attr, or a dict of them -- just make an attr or dict of lvals,
  and have the owning class access them differently.

For examples, see the classes herein whose names contain Lval.
'''

# WARNING: the code in here needs to be safe for use in implementing ExprsMeta, which means it should not depend
# on using that as a metaclass.

# == imports

# from modules in cad/src

from changes import SelfUsageTrackingMixin, SubUsageTrackingMixin

# from this exprs package

from basic import *

MemoDict # comes from py_utils via basic; very simple, safe for use in ExprsMeta [061024]

# ==

class Lval(SelfUsageTrackingMixin, SubUsageTrackingMixin):
    """One invalidatable value of the most standard kind,
    containing its own fully bound compute method, passed to the constructor.
       Get the current value using .get_value() (this tells the dynenv that this value was used).
    Contains inval flag, subs to what it used to compute, recomputes as needed on access, propogates invals,
    all in standard ways. [#doc better]
    Change the compute method using .set_compute_method.
    """
    # Implem notes:
    #
    # - This object can't be a Python descriptor (in a useful way), because its storage has to be per-instance.
    #   [I suppose we could separate it from its storage, and then that might not be true.
    #    But it's simpler this way, especially since we sometimes store one in a visibly-indexed dict rather than an object-attr.]
    # - If a descriptor (which has to be per-class) uses one of these, it has to look up the one to use in each instance.
    #   So the only reason not to provide this Lval with a bound recompute method would be to avoid cyclic references.
    #   At the moment, that's not crucial.
    # - When we want that, this still has the storage, but it can be given an owner obj each time it runs.
    #   It could just as well be given the compute method each time; for either one, the owner has to give the same one each time
    #   or the inval flag etc won't be correct.
    # - The compute method it's given (once or each time) could be a bound instance method (from a _C_attr method),
    #   or something created from a formula on _self, also bound to a value for _self. Whatever it is, we don't care how it's made,
    #   so we might as well accept any callable. It might be made in various ways, by descriptors or helper functions like LvalDict.
    #
    # - The mixins provide these methods, for internal use:
    #   - SelfUsageTrackingMixin: track_use, track_change == track_inval --
    #       for tracking how our value is used, is changed, is indirectly invalled.
    #   - SubUsageTrackingMixin: begin_tracking_usage, end_tracking_usage -- for tracking which values we use when we recompute.
    #   - They're the same mixins used for displists used by chunk/GLPane and defined in chunk, and for changes to env.prefs, 
    #     so these Lvals will work with those (except for chunk not yet propogating invals or tracking changes to its display list).
    #   - See comments near those methods in changes.py for ways they'll someday need extension/optimization for this use.
    valid = False
    # no need to have default values for _value, unless we add code to compare new values to old,
    # or for _compute_method, due to __init__
    def __init__(self, compute_method = None): #e rename compute_method -> recomputer?? prob not.
        """For now, compute_method is either None (meaning no compute_method is set yet -- error to try to use it until it's set),
        or any callable which computes a value when called with no args,
        which does usage-tracking of whatever it uses into its dynenv in the standard way
        (which depends mainly on what the callable uses, rather than on how the callable itself is constructed),
        and which returns its computed value (perhaps None or another callable, treated as any other value).
        Note that unlike the old InvalMixin's _recompute_ methods, compute_method is not allowed to use setattr
        (like the one we plan to imitate for it) instead of returning a value. (The error of it doing that is detected. ###k verify)
           In future, other special kinds of compute_methods might be permitted, and used differently,
        but for now, we assume that the caller will convert whatever it has into this simple kind of compute_method.
           [Note: if we try to generalize by letting compute_method be a python value used as a constant,
        we'll have an ambiguity if that value happens to be callable, so it's better to just make clients pass lambda:val instead.]
        """
        ## optim of self.set_compute_method( compute_method), only ok in __init__:
        self._compute_method = compute_method
    def set_compute_method(self, compute_method): # might be untested since might not be presently used
        old = self._compute_method
        self._compute_method = compute_method # always, even if equal, since different objects
        if old != compute_method:
            self.inval()
    def inval(self):
        """This can be called by the client, and is also subscribed internally to all invalidatable/usage-tracked lvalues
        we use to recompute our value (often not the same set of lvals each time, btw).
           Advise us (and whoever used our value) that our value might be different if it was recomputed now.
        Repeated redundant calls are ok, and are optimized to avoid redundantly advising whoever used our value
        about its invalidation.
           Note that this does not recompute the value, and it might even be called at a time
        when recomputing the value would be illegal. Therefore, users of the value should not (in general)
        recompute it in their own inval routines, but only when something next needs it. (This principle is not currently
        obeyed by the Formula object in changes.py. That object should probably be fixed (to register itself for
        a recompute later in the same user event handler) or deprecated. ###e)
        """
        if self.valid:
            self.valid = False
            # propogate inval to whoever used our value
            self.track_inval() # (defined in SelfUsageTrackingMixin)
    def get_value(self):
        """This is the only public method for getting the current value;
        it always usage-tracks the access, and recomputes the value if necessary.
        """
        if not self.valid:
            self._value = self._compute_value() # this catches exceptions in our compute_method
            self.valid = True
        # do standard usage tracking into env (whether or not it was invalid & recomputed) -- API is compatible with env.prefs
        # [do it after recomputing, in case the tracking wants to record _value immediately(?)]
        self.track_use() # (defined in SelfUsageTrackingMixin) ###e note: this will need optimization
        return self._value
    def _compute_value(self):
        """[private]
        Compute (or recompute) our value, using our compute_method but protecting ourselves from exceptions in it,
        tracking what it uses, subscribing our inval method to that.
        NOTE: does not yet handle diffing of prior values of what was used, or the "tracking in order of use" needed for that.
        Maybe a sister class (another kind of Lval) will do that.
        """
        #e future: _compute_value might also:
        # - do layer-prep things, like propogating inval signals from changedicts
        # - diff old & new
        assert self._compute_method is not None, "our compute_method is not yet set: %r" % self #e remove, as optim (redundant)
        match_checking_code = self.begin_tracking_usage()
        try:
            val = self._compute_method()
        except:
            print_compact_traceback("exception in %r._compute_method ignored: " % self)
            val = None
            if 1:
                printfyi("exiting right after lval exception, to see if it makes my errors more readable") ###k 061105; review
                ## import sys
                ## sys.exit(1) # doesn't work, just raises SystemExit which gets caught in the same way (tho not infrecur):
                import sys
                sys.stderr.flush() #k prob not needed
                sys.stdout.flush() #k prob needed
                import os
                os._exit(1) # from python doc for built-in exceptions, SystemExit
        self.end_tracking_usage( match_checking_code, self.inval )
            # that subscribes self.inval to lvals we used, and unsubs them before calling self.inval [###k verify that]
            #e optim (finalize) if set of used lvals is empty
            # (only if set_compute_method or direct inval won't be called; how do we know? we'd need client to "finalize" that for us.)
        # note: caller stores val and sets self.valid
        return val
    pass # end of class Lval

# ==

###@@@

class LvalForDrawingCode(Lval): #stub -- do we need this, or just pass an appropriate lambda to Lval? ##e
    """[deal with get_value returning side effects? or using .draw instead -- just internally?]
    """
    pass

class LvalForUsingASharedFormula(Lval): #stub -- do we need this? for a formula on _self shared among several instances
    """[pass _self to _compute_value?]
    """
    pass

## class LvalForDisplistEffects -- see DisplistChunk.py

# ==

def LvalDict(wayfunc, lvalclass = Lval): #e option to not memoize for certain types of keys (like trivials or errors)?? this or Memo?
    """An extensible dict of lvals of the given lval class, whose memoized values will be recomputed from dict key using wayfunc(key)().
    It's an error (reported [#nim] in MemoDict) for computation of wk = wayfunc(key) to use any external usage-tracked lvalues,
    but it's ok if wk() does; subsequent inval of those lvals causes the lval created here to recompute and memoize wk() on demand.
    This is more useful than if the entire dict had to be recomputed (i.e. if a _C_ rule told how to recompute the whole thing),
    since only the specific items that become invalid need to be recomputed.
       Design note: DO WE RETURN THE LVALS or their values??
    For now, WE RETURN THE LVALS (partly since implem is easier, partly since it's more generally useful);
    this might be less convenient for the user. [But as of 061117, staterefs.py will depend on this, in our variant LvalDict2.]
    """
    #k Note:
    # I'm only 90% sure the "wayfunc = wayfunc, lvalclass = lvalclass" lambda closure kluge is still needed in Python, in this case.
    # I know it's needed in some cases, but maybe only when they are variables??
    # More likely, whenever the lambda is used outside their usual scope, as it is in this case.
    return MemoDict( lambda key, wayfunc = wayfunc, lvalclass = lvalclass:
                     lvalclass( wayfunc(key)) )

def LvalDict2(valfunc, lvalclass = Lval):
    """Like LvalDict but uses a different recompute-function API, which might be easier for most callers to supply;
    if it's always better, it'll replace LvalDict.
    In this variant, just pass valfunc, which will be applied to key in order to recompute the value at key.
    """
    return MemoDict( lambda key, valfunc = valfunc, lvalclass = lvalclass:
                     lvalclass( lambda valfunc=valfunc, key=key: valfunc(key)) )
        
# end
