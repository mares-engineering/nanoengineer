# Copyright (c) 2004-2005 Nanorex, Inc.  All rights reserved.
"""
TreeWidget.py -- adds event handling and standard event bindings to TreeView.py.

[temporarily owned by Bruce, circa 050107, until further notice]

$Id$

History: modelTree.py was originally written by some combination of
Huaicai, Josh, and Mark. Bruce (Jan 2005) reorganized its interface with
Node and Group and their subclasses (Utility.py and other modules)
and rewrote a lot of the model-tree code (mainly to fix bugs),
and split it into three modules:
- TreeView.py (display and update),
- TreeWidget.py (event handling, and some conventions suitable for
  all our tree widgets, if we define other ones), and
- modelTree.py (customized for showing a "model tree" per se).
"""

from TreeView import * # including class TreeView, and import * from many other modules

class TreeWidget(TreeView, DebugMenuMixin):
    def __init__(self, parent, win, name = None, columns = ["node tree"]):
        """#doc
        creates all columns but only known to work for one column.
        some code only bothers trying to support one column.
        """
        ###@@@ review all init args & instvars, here vs subclasses
        TreeView.__init__(self, parent, win, name, columns = columns) # stores self.win

        self.setAcceptDrops(True)

        # debug menu and reload command ###e subclasses need to add reload actions too
        self._init_time = time.asctime() # for debugging; do before DebugMenuMixin._init1
        DebugMenuMixin._init1(self) ###e will this be too early re subclass init actions??

        ###@@@ soon obs, if not already:
        self.last_selected_node = None #k what's this for? ###@@@ mainly context menus?
         # actually it has several uses which need to be split:
         # - sometimes records last item user clicked on to select it (but not to unselect).
         # - tells context menu what to be about, if not asked for when over an item. [surely obs]
         # - used by context menu to record the item, if it *is* on an item. (even if it refuses to put up a menu) [surely obs]
         # - used as the "item to drag" in drag and drop (regardless of event posns or selection!). [obs]
            #bruce 050109 renamed this from selectedItem since that's
            # a Qt method in QListView! In theory this might fix bugs...
            # didn't notice any though.

        ###@@@ setCurrentItem might help it process keys... ###@@@ try it... maybe i did and it failed, not sure 050110

        self.setDefaultRenameAction(QListView.Accept)
            # I don't think this has any effect, now that we're depriving
            # QListView of mouse events, but I'm setting it anyway just in case.
            # The "real version of this" is in our own contentsMousePress... method.
        
        # bruce 050112 zapping most signals, we'll handle the events ourself.
        
        self.connect(self, SIGNAL("itemRenamed(QListViewItem*, int, const QString&)"), self.slot_itemRenamed)

        return # from TreeWidget.__init__

    # helper functions
    
    def fix_buttons(self, but, when):
        return fix_buttons_helper(self, but, when)
    
    def makemenu(self, lis):
        return makemenu_helper(self, lis)    

    # event processing & selection
    
    def contentsMouseDoubleClickEvent(self, event):
        "[called by Qt]"
        return self.contentsMousePressEvent(event, dblclick = 1)

    renaming_this_item = None
    def contentsMousePressEvent(self, event, dblclick = 0):
        "[called by Qt, or by our own contentsMouseDoubleClickEvent]"
        
        # figure out position and item of click (before doing any side effects)
        #e this might be split into a separate routine if it's useful during drag
        
        cpos = event.pos() # this is in contents coords;
            # y=1 is just under column label (which does not scroll with content)
        vpos = self.contentsToViewport(cpos)
        item = self.itemAt(vpos)
        
        # before anything else (except above -- in case this scrolls for some reason),
        # let this click finish an in-place renaming, if there was one.
        if self.renaming_this_item:
            self.renaming_this_item.okRename(0) # 0 is column # this ends up calling slot_itemRenamed
                # could this scroll the view? I doubt it, but if so,
                # it's good that we figured out cpos,vpos,item before that.
            self.done_renaming()
                # redundant with slot function, but i'm not sure that always runs or gets that far

        # now figure out what part of the item (if any) we clicked on,
        # setting 'part' to a constant string describing which part, or None.

        # (someday: if we clicked too far to left or right of visible part of item,
        #  set item = part = None; or we might have new 'part' values
        #  for those positions. #e)

        part = None
        ## clicked_on_text = clicked_on_icon = clicked_on_openclose = False
        if item:
            # where in the item did we click?
            # relevant Qt things:
            # QListViewItem::width - width of text in col k (without cropping)
            # ... and some example code for a directory browser (available in PyQt too... examples3/dirview.py)
##            ## here is the code from dirview.py:
##            # if the user clicked into the root decoration of the item, don't try to start a drag!
##            if self.rootIsDecorated(): isdecorated = 1
##            else : isdecorated = 0
##            #bruce 050120 observes that there's a misplaced ')' in the next line. compare to Qt version of this.
##            if p.x() > self.header().sectionPos( self.header().mapToIndex( 0 )) + self.treeStepSize() * ( i.depth() + isdecorated + self.itemMargin() or
##               p.x() < self.header().sectionPos( self.header().mapToIndex( 0 ) ) ) : ### to left of this column
##               self.presspos.setX(event.pos().x())
##               self.presspos.setY(event.pos().y())
##               self.mousePressed = True
            # our version of dirview example's code:
            isdecorated = 1 # should conform to self.rootIsDecorated()
            header = self.header()
            special_x = header.sectionPos( header.mapToIndex( 0 ))
                # where is this x? by experiment it's always 0 for us. must be left edge of column 0.
                # btw, Qt C++ eg uses mapToActual but there's no such attr when tried here.
            extra = self.treeStepSize() * (item.depth() + isdecorated) + self.itemMargin()
            ## special_x_2 = header.sectionPos( header.mapToActual( 0 )) # no such attr
##            print "for that item: special x pos = %r, treestep = %r, depth %r, margin %r" % (
##                                        special_x, self.treeStepSize(), item.depth(), self.itemMargin() )
            greater_by = vpos.x() - (special_x + extra) # this tells whether we hit the left edge of the icon, for a very big icon.
##            if greater_by > 0:
##                print "to right of decoration by",greater_by # i think to right by 3 or 2 should count as on decoration...
##            else:
##                print "not to right",greater_by
            if greater_by > 22: #e probably need to adjust this cutoff
                part = 'text'
                #e incorrect if we're to the right of the visible text;
                # Qt docs show how to check text width to find out; should use that
                # (also we're not checking for still being in column 0, just assuming that)
            if greater_by > 2: #e might need to adjust this cutoff (btw it's a bit subjective)
                part = 'icon'
            elif greater_by > -12: ###e surely need to adjust this
                part = 'openclose'
                print "change so openclose can only happen for an expandable item" ####@@@@
            elif vpos.x() >= special_x:
                part = 'left'
            else:
                part = item = None # to the left of column 0 (not currently possible I think)
            pass
        
        # If this click's data differs from the prior one, this event shouldn't
        # be counted as a double click. Or the same, if too much time passed since prior click,
        # which would mean Qt erred and called this a double click even though its first click
        # went to a different widget (I don't know if Qt can make that mistake).
        # ###e nim feature... ###@@@

        ###e probably store some things here too, in case we'll decide later to start a drag.

        self.clicked( event, vpos, item, part, dblclick)

        self.update_select_mode() # change user-visible mode to selectMolsMode iff necessary
        
        return # from contentsMousePressedEvent

    def contentsMouseMoveEvent(self, event): ###e extend for drag & drop (or use other method? still need this one); use fix_buttons
        "[overrides QListView method]"
        # This method might be needed, to prevent QListView's version of it from messing us up.
        pass
    
    def contentsMouseReleaseEvent(self, event): ###e extend for drag & drop; use fix_buttons
        "[overrides QListView method]"
        # This method might be needed, to prevent QListView version of it from messing us up.
        # (At least, without it, QListView emits its "clicked" signal.)
        pass 

    def update_select_mode(self): #bruce 050124; this should become a mode-specific method and be used more generally.
        """This should be called at the end of event handlers which might have
        changed the current internal selection mode (atoms vs chunks),
        to resolve disagreements between that and the visible selection mode
        iff it's one of the Select modes. If the current mode is not one of
        Select Atoms or Select Chunks, this routine has no effect.
           If possible, we leave the visible mode the same (even changing assy.selwhat
        to fit, if nothing is actually selected). But if forced to, by what is
        currently selected, then we change the visible selection mode to fit
        what is actually selected.
        """
        #e should optim: this can call repaintGL redundantly
        # with win.win_update() [bruce 041220; is this still true? 050124]
        mode = self.win.glpane.mode
        if not isinstance(mode, selectMode):
            return
        if assy.selatoms and isinstance( mode, selectMolsMode):
            self.win.toolsSelectAtoms() ###k check tool name - this case not needed by treewidget
        elif assy.selmols and isinstance( mode, selectAtomsMode):
            self.win.toolsSelectMolecules()
        else:
            pass # nothing selected -- don't worry about assy.selwhat
        return

    # command bindings for clicks on various parts of tree items
    # are hardcoded in the 'clicked' method:
    
    def clicked( self, event, vpos, item, part, dblclick):
        """Called on every mousedown (regardless of mouse buttons / modifier keys).
        Event is the Qt event (not yet passed through fix_buttons).
        vpos is its position in viewport coordinates.
        item is None or a QListViewItem.
        If item, then part is one of ... #doc; otherwise it's None.
        dblclick says whether this should count as a double click
        (note that for some bindings we'll implement, this won't matter).
        (Note that even if dblclick can be determined directly from event,
        caller might have its own opinion, which is what we use, so the flag
        would need to be separately passed anyway.)
        """

        # handle debug menu; canonicalize buttons and modifier keys.
        
        if self.debug_event(event, 'mousePressEvent', permit_debug_menu_popup = 1):
            return
        but = event.stateAfter()
        but = self.fix_buttons(but, 'press')

        # Now check for various user commands, performing the first one that applies,
        # and doing whatever inval or update is needed within the tree widget itself,
        # but not necessarily all needed external updates (some of these are done
        # by our caller).
        
        # handle context menu request.
        
        if but & rightButton:
            # This means we want a context menu, for the given item
            # (regardless of which part of it we clicked on (even openclose or left)!),
            # or for a set of selected items which it's part of
            # (this is detected in following subr), or for no item if item == None.
            # The menu (and the selection-modifying behavior before we put it up) can ignore modifier keys and dblclick.
            ###k [verify it ignores modkeys rather than having them defeat the menu, in the mac]
            pos = event.globalPos()
            self.menuReq( item, pos) # does all needed updates ###k even in glpane?
            return

        # after this point, treat clicks to left of open/close icon as if on no item.
        # (would it be better to treat them as on open/close, or have a special cmenu
        #  about the parent items, letting you close any of those? ##e)
        if part == 'left':
            part = item = None
        
        # handle open/close toggling. (ignores modifier keys, mouse buttons, dblclick)
        if part == 'openclose':
            # this can only happen for a non-leaf item!
            self.toggle_open(item) # does all needed inval/update/repaint ####@@@@ is this finished?
            return

        # handle in-place editing of the item text, on double-click
        
        #e (someday this might be extended to edit a variant of the text,
        #   if some of it is a fixed label or addendum... to implem that,
        #   just call item.setText first, within the subroutine.)

        # (for now, this is done for middle click too, and it ignores modifier keys)
        if dblclick and part = 'text':
            # presumably the first click selected this item... does this matter?? #k
            # BTW it would not be true if this was a Control-double-click!
            # If we wanted to be paranoid, we'd return unless the modkeys and button
            # were identical with the saved prior click (and were null)... #e do that now? ###@@@
            col = 0
            return self.maybe_beginrename( item, vpos, col)

        # what's left?
        # - selection.
        # - drag-starting, whether for d&d or (saved for later #e) a selection range or rect.
        # - hover behaviors (tooltip, cmenu) (saved for later. #e)
        #####@@@@ need code to save event info for drag-starting ###@@@ merge with selection_click, elsewhere

        # selection-click, and/or start of a drag
        # (we can't in general distinguish these until more events come)

        if dblclick:
            # Too likely this 2nd click was a mistake -- let the first click handle
            # it alone. (This only matters for Control-click, which toggles selection,
            # once the feature of discarding dblclick flag when item/part
            # changed is implemented.)
            return

        # if buttons are not what we expect, return now (thus avoiding bad effects
        # from some possible bugs in the above code)
        allButtons = (leftButton|midButton|rightButton)
        if (but & allButtons) is not in [leftButton, midButton]:
            # (note, this is after fix_buttons, so on Mac this means click or option-click)
            return

        drag_should_copy = but & midButton # standard for Mac; don't know about others
        drag_type = (drag_should_copy and 'copy') or 'move'

        # set modifier (NOT self.modifier!) for compatibility with old code's select() routine
        if but & (shiftButton|cntlButton):
            modifier = 'ShiftCntl' # (except this one is new)
        elif but & shiftButton:
            modifier = 'Shift'
        elif but & cntlButton:
            modifier = 'Cntl'
        else:
            modifier = None

        self.selection_click( item,
                              modifier = modifier,
                              group_select_kids = (part == 'icon'), ##k ok? nim anyway ###@@@ must fix for cmenu
                              permit_drag_type = drag_type )
        
        return # from clicked

    # context menu requests (the menu items themselves are defined by our subclass)
    
    def menuReq(self, item, pos):
        """Context menu items function handler for the Model Tree View
        [interface is mostly compatible with a related QListView signal,
         but it's no longer called that way; col arg was not used and is now removed;
         pos should be the position to put up the menu, in global coords (event.globalPos).]
        """
        # First, what items should this context menu be about?
        #
        # Here's what the Mac (OS 10.2) Finder does:
        #
        # (btw, for the mac, context menus are asked for by control-click,
        #  vs. right-click on other platforms -- here I'll say context-click:)
        #
        # - If you context-click on a selected item, the menu is about
        # the set of (one or more) selected items, which does not change.
        #
        # - If you context-click on another item, the selection changes to
        # include just the item you clicked on (and you can see that in
        # the selection highlighting), and the menu is about *that* item.
        #
        # - If you click on no item, you get a menu for the window as a whole
        # (whether or not items were selected; if any were, they are unselected).
        #
        # Furthermore, when the menu is about a set of more than one items,
        # the text of its entries makes this clear.
        #
        # (What about other modifier keys which normally modify selection
        # behavior? If you use them, it just does selection and ignores the
        # control key (no context menu). This is not what our caller does
        # as of 050124, but I don't think it matters much... ##e)
        #
        # Note that this implies: the visible selection always shows you what
        # set of items the context menu is about and will operate on; it's easy
        # to make the menu be about the existing selection, or about no items,
        # or (usually) about any existing single item; the only harder case for
        # the user is when you want a menu about one item, and it and others are
        # selected, in which case, you just click somewhere (to unselect all)
        # and then context-click on the desired item; if instead you don't notice
        # that any other items are selected, you'll notice your mistake when you
        # see the text of the menu entries.
        #
        # BTW, if you click on an "open/close icon" (or to the left of an item),
        # it acts like you clicked on no item, for this purpose. (As of 050124
        # our caller behaves differently in this case too, on purpose I guess...)
        #
        # [refile?] About the menu position and duration:
        # In all cases, the menu top left corner is roughly at the click pos,
        # and the menu disappears immediately on mouseup, whether or not you
        # choose a command from it. [That last part is nim since I don't yet
        # know how to make it happen.]
        #
        # This all seems pretty good, so I will imitate it here. [bruce 050113]

        #e correct item to be None if we were not really on the item acc'd to above?
        # no, let the caller do that, if it needs to be done.
        self.selection_click( item, modifier = None, group_select_kids = False, permit_drag_type = None)

        ####@@@@ revise the following
        
        set = self.current_selection_set() # a list of items?? might be a more structured thing someday... and/or made of nodes...
            # but i think it's items for now, since some ops really involve them as items more than as nodes...
            # otoh not all of the selected nodes might have real items in the widget, but all should be in this...
            # otth we can make item proxies for them even if those don't own real tree items at the moment...
            # and probably we should...
            # so it's a list of items for now.
        menu = self.make_cmenu_for_set( set)
        print "arg1 of qmpopup is menu = %r, other arg pos is %r" % (menu,pos)#####@@@@@@
        menu.popup(pos) ##### transform pos #e care about which item to put where (e.g. popup(pos,1))?
        # bruce comment 050110: following mt_update is probably not helping anything ###@@@ try removing it; try exec_loop?
        # since the menu has just been put up -- nothing has yet been chosen from it
        self.dprint("mtree.menuReq just returned from menu.popup, probably with menu there - what events are responded to?")###@@@ find out!
        self.mt_update()
        ###e also glpane update? eg for hide, select all... ####@@@@
        return
    
    def make_cmenu_for_set(self, itemset):
        """Return a context menu (QPopupMenu object #k)
        to show for the given set of (presumably selected) items.
        [Might be overridden by subclasses, but usually it's more convenient
        for them to override make_cmenuspec_for_set instead.]
        """
        spec = self.make_cmenuspec_for_set(itemset)  \
               or self.make_cmenuspec_for_set([])  \
               or [('(empty context menu)',noop,'disabled')]
        return self.makemenu( spec)

    def make_cmenuspec_for_set(self, itemset):
        """#doc
        [subclasses should override this]
        # [see also the term Menu_spec]
        """
        return []

    # selection logic
    
    def selection_click(self, item, _guard_ = None, group_select_kids = True, modifier = None, permit_drag_type = None):
        """Perform the ordinary selection-modifying behavior for one click on this item (might be None).
        Assume the modifier keys for this click were as given in modifier, for purposes of selection or drag(??) semantics.
        We immediately modify the set of selected items -- changing the selection state of their Nodes (node.picked),
        updating tree-item highlighting (but not anything else in the application -- those will be updated when Qt resumes
         event processing after we return from handling this click ###@@@ so we need to inval the glpane to make that work!
         until then, it won't update til... when? the next paintGL call. hmm. I guess we just have to fix this now.).
    
        If permit_drag_type is not None, this click might become the start of a drag of the same set of items it
        causes to be selected; but this routine only sets some instance variables to help a mouse move method decide whether
        to do that. The value of permit_drag_type should be 'move' or 'copy' according to which type of drag should be done
        if it's done within this widget. (If the drop occurs outside this widget, ... #doc)
        
        #doc elsewhere: for a single plain click on a selected item, this should not unselect the other items!
        # at least finder doesn't (for sel or starting a drag)
        # and we need it to not do that for this use as well.
        """
        assert not _guard_, "you passed too many positional arguments to this function!"
        
##        ### this is not used in place of select yet, just to test cmenus...
##        # (which in any case will be passed to us, not found in some attribute on self! since some callers filter them.)
##
##        #e first filter item and pos so that positions too far to left or right don't count as being on item. NIM.
##        # one case of this is clicks on the open/close togging icon. Not sure if they ever get here, though,
##        # in fact, caller might do this filtering. We'll see.
##        
##        if item and item.object.picked: ###@@@ does this depend on modkeys?? ###@@@ do stuff to set up for drag, too
##            return # no change! #doc why; see comments in menuReq
##
##        #e now perform sel logic... using item none or not, and modkeys... update .picked and item highlighting. ####@@@@
##        ####@@@@ implem... steal some code from select, or split it into this...
##        # stub: just toggle it for this one item. wait, above behavior defeats this... too tired, do this tomorrow.
##        if item:
##            node = item.object
##            if node.picked:
##                node.unpick() # won't happen yet...
##            else:
##                node.pick()

        self.select_0( item, group_select_kids, modifier, permit_drag_type) # does no updating?? or is that too inefficient?

        ###@@@ only sometimes do the following? have our own inval flags for these? 
        self.update_selection_highlighting() ###@@@ remove this from select_0?
        self.win.glpane.update() ####k will this work already, just making it call paintGL? or must we inval something too??
        return
    
    def select_0(self, item, group_select_kids, modifier, permit_drag_type):
        "item is a list view item or none"
        ###@@@ maybe some (in this or a few callers) belongs in the subclass?
        # bruce comment 041220: this is called when widget signals that
        # user clicked on an item, or on blank part of model tree (confirmed by
        # experiment). Event (with mod keys flags) would be useful...
        # 
        self.dprint("select called")

        assert group_select_kids, "group_select_kids being F is nim, but we need it!" ####@@@@
        
##        if item:
##            if isinstance(item, PartGroup):
##                self.dprint("select returns early since item is the PartGroup") #k (but why can't we select it?)
##                return
##            if item.object.name == self.assy.name:
##                self.dprint("select would have returned early since item.object.name == self.assy.name; but it doesn't now")
##                # don't return
        
##        self.win.assy.unpickatoms() # belongs in the subclass... in fact, no reason to ever do this [bruce 050124]

        # Note: the following behavior uses Shift and Control sort of like the
        # GLPane (and original modelTree) do, but in some ways imitates the Mac
        # and/or the QListView behavior; in general the Mac behavior is probably
        # better (IMHO) and maybe we should imitate it more. (For example, I'm
        # very skeptical of the goodness of applying pick or unpick to entire
        # subtrees as the default behavior; for now I refrained from changing
        # that, but added a new mod-key-pair ShiftCntl to permit defeating it.)
        # [bruce 050124]

        #e This needs some way to warn the user of what happens in subtrees
        # they can't see (when nodes are openable but closed, or even just with
        # their kids scrolled out of sight). Probably best is to always show
        # sel state of kids in some manner, right inside each Group's item. #e

        # warning: in future the pick and unpick methods we're calling here
        # might call incremental updaters back in this module or treeview!
        
        if modifier == 'ShiftCntl': # bruce 050124 new behavior [or use Option key? #e]
            # toggle the sel state of the clicked item ONLY (no effect on members);
            # noop if no item.
            if item:
                if item.object.picked:
                    item.object.unpick_top()
                else:
                    item.object.pick_top()
                print "update nim"
        elif modifier == 'Cntl':
            # unselect the clicked item (and all its members); noop if no item.
            if item:
                item.object.unpick()
                print "update nim"
        elif modifier == 'Shift':
            # Mac would select a range... but I will just add to the selection,
            # for now (this item and all its members); noop for no item.
            if item:
                # whether or not item.object.picked -- this matters
                # for groups with not all picked contents!
                item.object.pick()
                print "update nim"
        else:
            # no modifier (among shift and control anyway)...
            if item:
                if item.object.picked:
                    # must be noop when item already picked, in case we're
                    # starting a drag of multiple items
                    pass
                else:
                    # deselect all items except this one
                    for node in self.topnodes:
                        node.unpick()
##                    ###e (within the "current space"??? maybe not, maybe the whole tree... not sure)
##                    ####@@@@ also make that a barrier for descending into selstate of members? yes... not sure; not yet i guess
##                    ## item.object.assy.unpickparts() ####@@@@ this will change somehow... really should use our own top nodes! topnodes
                    item.object.pick()
                    print "update nim"
            else:
                # no item
                for node in self.topnodes:
                    node.unpick()
                print "update nim"
        # that should do it!
        
        self.update_selection_highlighting() ####@@@@ does this work? do it in caller (like we do?)
        return

    # key events ###@@@ move these?
    
    def keyPressEvent(self, event): ####@@@@ Delete needs revision, and belongs in the subclass
        key = event.key()
        import platform
        key = platform.filter_key(key) #bruce 041220 (needed for bug 93)
        if key == Qt.Key_Delete: ####@@@@ belongs in the subclass
            # bruce 041220: this fixes bug 93 (Delete on Mac) when the model
            # tree has the focus; the fix for other cases is in separate code.
            # Note that the Del key (and the Delete key on non-Mac platforms)
            # never makes it to this keyPressEvent method, but is handled at
            # some earlier stage by the widget, and in a different way;
            # probably this happens because it's a menu item accelerator.
            # The Del key (or the Delete menu item) always directly runs
            # MWsemantics.killDo, regardless of focus.
            self.win.killDo()
            ## part of killDo: self.win.win_update()
##        ###@@@ the rest is soon to be obs
##        elif key == Qt.Key_Control:
##            self.modifier = 'Cntl' ###@@@ soon to be obs
##        elif key == Qt.Key_Shift:
##            self.modifier = 'Shift' ###@@@ soon to be obs
        # bruce 041220: I tried passing other key events to the superclass,
        # QListView.keyPressEvent, but I didn't find any that had any effect
        # (e.g. arrow keys, letters) so I took that out.
        return
        
    def keyReleaseEvent(self, event):
        pass
##        self.modifier = None ###@@@ soon to be obs


    # selection helpers - might be #OBS ###@@@
    
    def item_is_selected(self, item): ###@@@ might work in superclass but only useful here and might be redefined here
        """Is the given item already selected?
        (Special case: for item == None (legal), return False.)
        """
        if not item:
            return False
        return item.isSelected() #k guess ###@@@stub, not sure this is the right/best/ok place to store this state

    def current_selection_set(self):
        if not hasattr(self, 'selected_items'):
            self.selected_items = [] # see also comments/samecode just above
        return list(self.selected_items)


    # in-place editing of item text
    
    def maybe_beginrename(self, item, pos, col):
        """Calls the Qt method necessary to start in-place editing of the given item's name.
        Meant to be called as an event-response; presently called for double-click on the name.
        """
        self.dprint("maybe_beginrename(%r, %r, %r)"%(item,pos,col))
        if not item: return
        if col != 0: return
        if not item.renameEnabled(col): return ####@@@@ 050119 exper; should be enough to stop renaming of Clipboard ###test
        istr = str(item.text(0))
        ## now done by rename disabled in their node subclasses: ###@@@ test
        ## if istr in [self.assy.name, "Clipboard"]: return
        msg = "(renaming %r -- complete this by pressing Return, or cancel it by pressing Escape)" % istr
        self.win.history.transient_msg( msg)
            # this happened even for a Datum plane object for which the rename does not work... does it still? ###@@@
            # bug: that message doesn't go away if user cancels the rename.
        self.renaming_this_item = item # so we can accept renaming if user clicks outside the editfield for the name
        item.startRename(0)

    ###@@@ does any of this belong in the subclass??
    def slot_itemRenamed(self, item, col, text): # [bruce 050114 renamed this from changename]
        "receives the signal from QListView saying that the given item has been renamed"
        self.dprint("slot_itemRenamed(%r, %r, %r)" % (item,col,text))
        if col != 0: return
        oldname = self.done_renaming()
        what = (oldname and "%r" % oldname) or "something" # not "node %r"
        del oldname
        # bruce 050119 rewrote/bugfixed the following, including the code by
        # Huaicai & Mark to strip whitespace, reject null name, and update
        # displayed item text if different from whatever ends up as the node's
        # name; moved much of that into Node.try_rename.
        text = str(text) # turn QString into python string
        # use text (not further changed) for comparison with final name
        (ok, newname) = item.object.try_rename(text) #e pass col?
        if ok:
            res = "renamed %s to %r" % (what, newname)
        else:
            res = "can't rename %s to %r" % (what, newname) #e redmsg too?
        if text != newname:
            # (this can happen for multiple reasons, depending on Node.try_rename:
            #  new name refused, whitespace stripped, etc)
            # update the display to reflect the actual new name
            # (might happen later, too, if try_rename invalidated this node;
            #  even so it's good to do it now so user sees it a bit sooner)
            item.setText(col, newname)
        self.win.history.message(" (%s)" % res)
        return # no need for more mtree updating than that, I hope (maybe selection? not sure)

    def done_renaming(self):
        "call this when renaming is done (and if possible when it's cancelled, tho I don't yet know how)"
        try:
            oldname = self.renaming_this_item.object.name
        except:
            oldname = ""
        self.renaming_this_item = None
        self.win.history.transient_msg("")
        return oldname

    # drag and drop (ALL DETAILS ARE WRONG AND OBS ###@@@)
    
    ###@@@ bruce 050110 - this overrides a Qt method, is that intended?? the one we should override is dragObject
    ####@@@@ let's try ths change
##    def startDrag(self): 
#        print "MT.startDrag: self.last_selected_node = [",self.last_selected_node,"]"
##        if self.last_selected_node:
##            foo = QDragObject(self)
##            foo.drag()
    def dragObject(self):
        self.dprint("dragObject, last_selected_node is %r" % self.last_selected_node)
        if self.last_selected_node: # Qt doc says "depending on the selected nodes"
            foo = QDragObject(self)
            return foo
            ##foo.drag()

    def dropEvent(self, event):
        above = False
        pnt = event.pos() - QPoint(0,24)
        # mark comments [04-12-10]
        # We need to check where we are dropping the selected item.  We cannot allow it 
        # to be dropped into the Data group.  This is what we are checking for here.
        # mmtop = 5 top nodes * (
        #                treeStepSize (space b/w parent and child nodes = 20 pixels) + 
        #                5 pixels (space b/w nodes ))
        mttop = 5 * (self.treeStepSize() + 5) # Y pos past top 5 nodes of MT (after last datum plane node).
#        print "modelTree.dropEvent: mttop = ",mttop
        if pnt.y() < mttop:
            pnt.setY(mttop) # We dropped above the first chunk (onto datum plane/csys). Mark 041210
            above = True # If we move node, insert it above first node in MT.
        droptarget = self.itemAt(self.contentsToViewport(pnt))
        if droptarget:
# bruce 050121 removing all these obs special cases, even tho not yet replaced with revised ones,
# since these entire routines are all wrong and will be totally replaced.
##            sdaddy = self.last_selected_node.whosurdaddy() # Selected item's daddy (source)
##            tdaddy = droptarget.object.whosurdaddy() # Drop target item's daddy (target)
###            print "Source selected item:", self.last_selected_node,", sdaddy: ", sdaddy
###            print "Target drop item:", droptarget.object,", tdaddy: ", tdaddy
##            if sdaddy == "Data": return # selected item is in the Data group.  Do nothing.
##            if sdaddy == "ROOT": return # selected item is the part or clipboard. Do nothing.    
            if isinstance(droptarget.object, Group): above = True # If drop target is a Group
            self.last_selected_node.moveto(droptarget.object, above)
#            if sdaddy != tdaddy: 
#                if sdaddy == "Clipboard" or droptarget.object.name == "Clipboard": 
#                    self.win.win_update() # Selected item moved to/from clipboard. Update both MT and GLpane.
#                    return
#            self.mt_update() # Update MT only
            self.win.win_update()

    def dragMoveEvent(self, event):
        event.accept()

    # debug menu items

    def debug_menu_items(self):
        "overrides method from DebugMenuMixin"
        super = DebugMenuMixin
        usual = super.debug_menu_items(self)
            # list of (text, callable) pairs, None for separator
        ours = [
                ("reload TreeWidget.py", self._reload_TreeWidget),
                ("reload modelTree.py", self._reload_modelTree), ###@@@ mnove to subclass?
                ("(treewidget instance created %s)" % self._init_time, lambda x:None, 'disabled'),
                ]
        ours.append(None)
        ours.extend(usual)
        return ours

    def _reload_this_module(self): ####@@@@ revise for my having split the modules, maybe move some to subclass...
        """reload this module, and replace the existing tree widget
        with a new one made from the new module"""
        # for now we might just plop the new one over the existing one! hope that works.
        print "\n_reload_this_module (modelTree.py I assume)"
        import modelTree
        reload(modelTree)
        from modelTree import modelTree
        # figure out where we are
        splitter = self.parent()
        print "splitter:",splitter # QSplitter
        win = self.win
        # imitate MWsemantics.py: Create the model tree widget
        win.mt = win.modelTreeView = modelTree(splitter, win)
        win.modelTreeView.setMinimumSize(0, 0)
        # at this point the new widget is probably to the right of the glpane! hmm...
        splitter.moveToFirst(win.mt)
        # (do we also need to show it? and hide this one? can't hurt. might not work for childwidgets?)
        win.mt.show()
        self.hide()
        print "done reloading... I guess"
        win.history.message( "reloaded model tree, init time %s" % win.mt._init_time)
        return

    _reload_TreeWidget = _reload_modelTree = _reload_this_module ####@@@@

    pass # end of class TreeWidget

# end

