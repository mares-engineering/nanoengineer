# Copyright (c) 2005 Nanorex, Inc.  All rights reserved.
'''
bond_constants.py -- constants for higher-order bonds, and related simple functions.

$Id$

History:

050429 - Started out as part of bonds.py. Gradually extended.

050707 - Split into separate file, largely to avoid recursive import problems
(since these constants need to be imported by many bond-related modules).
Many of them are still imported via bonds module, by code in other modules.
'''
__author__ = 'bruce'

import platform
from VQT import Q
from math import floor, ceil #guess

# Bond valence constants -- exact ints, 6 times the numeric valence they represent.
# If these need an order, their standard order is the same as the order of their numeric valences
# (as in the constant list BOND_VALENCES).

V_SINGLE = 6 * 1
V_GRAPHITE = 6 * 4/3  # (this can't be written 6 * (1+1/3) or 6 * (1+1/3.0) - first one is wrong, second one is not an exact int)
V_AROMATIC = 6 * 3/2
V_DOUBLE = 6 * 2
V_CARBOMERIC = 6 * 5/2 # for the bonds in a carbomer of order 2.5 (which alternate with aromatic bonds); saved as bonda for now [050705]
V_TRIPLE = 6 * 3

V_UNKNOWN = 6 * 7/6 # not in most tables here, and not yet used; someday might be used internally by bond-type inference code

BOND_VALENCES = [V_SINGLE, V_GRAPHITE, V_AROMATIC, V_DOUBLE, V_CARBOMERIC, V_TRIPLE]
BOND_MMPRECORDS = ['bond1', 'bondg', 'bonda', 'bond2', 'bonda', 'bond3'] # duplication of bonda is intentional (for now)
    # (Some code might assume these all start with "bond".)
    # (These mmp record names are also hardcoded into mmp-reading code in files_mmp.py.)
bond_type_names = {V_SINGLE:'single', V_DOUBLE:'double', V_TRIPLE:'triple',
                   V_AROMATIC:'aromatic', V_GRAPHITE:'graphite', V_CARBOMERIC:'carbomeric'}

BOND_VALENCES_HIGHEST_FIRST = list(BOND_VALENCES)
BOND_VALENCES_HIGHEST_FIRST.reverse()

V_ZERO_VALENCE = 0 # used as a temporary valence by some code

BOND_LETTERS = ['?'] * (V_TRIPLE+1) # modified just below, to become a string; used in initial Bond.draw method via bond_letter_from_v6

for v6, mmprec in zip( BOND_VALENCES, BOND_MMPRECORDS ):
    BOND_LETTERS[v6] = mmprec[4] # '1','g',etc
    # for this it's useful to also have '?' for in-between values but not for negative or too-high values,
    # so a list or string is more useful than a dict

BOND_LETTERS[V_CARBOMERIC] = 'c' # not 'a', not 'b'

BOND_LETTERS[0] = '0' # see comment in bond_letter_from_v6

BOND_LETTERS = "".join(BOND_LETTERS)
    ## print "BOND_LETTERS:",BOND_LETTERS # 0?????1?ga??2?????3

BOND_MIN_VALENCES = [ 999.0] * (V_TRIPLE+1) #bruce 050806; will be modified below
BOND_MAX_VALENCES = [-999.0] * (V_TRIPLE+1)

bond_valence_epsilon = 1.0 / 64 # an exact float; arbitrary, but must be less than 1/(2n) where no atom has more than n bonds

for v6 in BOND_VALENCES:
    if v6 % V_SINGLE == 0: # exact valence
        BOND_MIN_VALENCES[v6] = BOND_MAX_VALENCES[v6] = v6 / 6.0
    else:
        # non-integral (and inexact) valence
        BOND_MIN_VALENCES[v6] = floor(v6 / 6.0) + bond_valence_epsilon
        BOND_MAX_VALENCES[v6] = ceil(v6 / 6.0)  - bond_valence_epsilon
    pass

BOND_MIN_VALENCES[V_UNKNOWN] = 1.0 # guess, not yet used
BOND_MAX_VALENCES[V_UNKNOWN] = 3.0 # ditto

def min_max_valences_from_v6(v6):
    return BOND_MIN_VALENCES[v6], BOND_MAX_VALENCES[v6]

def bond_letter_from_v6(v6): #bruce 050705
    """Return a bond letter summarizing the given v6,
    which for legal values is one of 1 2 3 a g b,
    and for illegal values is one of - 0 ? +
    """
    try:
        ltr = BOND_LETTERS[v6]
            # includes special case of '0' for v6 == 0,
            # which should only show up for transient states that are never drawn, except in case of bugs
    except IndexError: # should only show up for transient states...
        if v6 < 0:
            ltr = '-'
        else:
            ltr = '+'
    return ltr

def btype_from_v6(v6): #bruce 050705
    """Given a legal v6, return 'single', 'double', etc.
    For illegal values, return 'unknown'.
    For V_CARBOMERIC this returns 'carbomeric', not 'aromatic'.
    """
    try:
        return bond_type_names[v6]
    except KeyError:
        if platform.atom_debug:
            print "atom_debug: illegal bond v6 %r, calling it 'unknown'" % (v6,)
        return 'unknown' #e stub for this error return; should it be an error word like this, or single, or closest legal value??
    pass

def invert_dict(dict1): #bruce 050705
    res = {}
    for key, val in dict1.items():
        res[val] = key
    return res

bond_type_names_inverted = invert_dict(bond_type_names)

def v6_from_btype(btype): #bruce 050705
    "Return the v6 corresponding to the given bond-type name ('single', 'double', etc). Exception if name not legal."
    return bond_type_names_inverted[btype]

def bonded_atoms_summary(bond, quat = Q(1,0,0,0)): #bruce 050705
    """Given a bond, and an optional quat describing the orientation it's shown in,
    order the atoms left to right based on that quat,
    and return a text string summarizing the bond
    in the form C26(sp2) <-2-> C34(sp3) or so.
    """
    a1 = bond.atom1
    a2 = bond.atom2
    vec = a2.posn() - a1.posn()
    vec = quat.rot(vec)
    if vec[0] < 0.0:
        a1, a2 = a2, a1
    a1s = describe_atom_and_atomtype(a1)
    a2s = describe_atom_and_atomtype(a2)
    bondletter = bond_letter_from_v6(bond.v6)
    if bondletter == '1':
        bondletter = ''
    return "%s <-%s-> %s" % (a1s, bondletter, a2s)

def describe_atom_and_atomtype(atom): #bruce 050705, revised 050727 #e refile?
    """Return a string like C26(sp2) with atom name and atom hybridization type,
    but only include the type if more than one is possible for the atom's element
    and the atom's type is not the default type for that element.
    """
    res = str(atom)
    if atom.atomtype is not atom.element.atomtypes[0]:
        res += "(%s)" % atom.atomtype.name
    return res

# ==

# Here's an old long comment which is semi-obsolete now [050707], but which motivates the term "v6".
# Note that I'm gradually replacing the term "bond valence" with whichever of "bond order" or "bond type"
# (related but distinct concepts) is appropriate. Note also that all the bond orders we deal with in this code
# are "structural bond orders" (used by chemists to talk about bonding structure), not "physical bond orders"
# (real numbers related to estimates of occupancy of molecular orbitals by electrons).

#bruce 050429: preliminary plan for higher-valence bonds (might need a better term for that):
#
# - Bond objects continue to compare equal when on same pair of atoms (even if they have a
# different valence), and (partly by means of this -- probably it's a kluge) they continue
# to allow only one Bond between any two atoms (two real atoms, or one real atom and one singlet).
#
# - I don't think we need to change anything basic about "internal vs external bonds",
# coordinates, basic inval/draw schemes (except to properly draw new kinds of bonds),
# etc. (Well, not due to bond valence -- we might change those things for other reasons.)
#
# - Each Bond object has a valence. Atoms often sum the valences of their bonds
# and worry about this, but they no longer "count their bonds" -- at least not as a
# substitute for summing the valences. (To prevent this from being done by accident,
# we might even decide that their list of bonds is not really a list, at least temporarily
# while this is being debugged. #?)
#
# This is the first time bonds have any state that needs to be saved,
# except for their existence between their two atoms. This will affect mmpfile read/write,
# copying of molecules (which needs rewriting anyway, to copy jigs/groups/atomsets too),
# lots of things about depositMode, maybe more.
#
# - Any bond object can have its valence change over time (just as the coords,
# elements, or even identities of its atoms can also change). This makes it a lot
# easier to write code which modifies chemical structures in ways which preserve (some)
# bonding but with altered valence on some bonds.
#
# - Atoms might decide they fit some "bonding pattern" and reorder
# their list of bonds into a definite order to match that pattern (this is undecided #?).
# This might mean that code which replaces one bond with a same-valence bond should do it
# in the same place in the list of bonds (no idea if we even have any such code #k).
#
# - We might also need to "invalidate an atom's bonding pattern" when we change anything
# it might care about, about its bonds or even its neighboring elements (two different flags). #?
#
# - We might need to permit atoms to have valence errors, either temporarily or permanently,
# and keep track of this. We might distinguish between "user-permitted" or even "user-intended"
# valence errors, vs "transient undesired" valence errors which we intend to automatically
# quickly get rid of. If valence errors can be long-lasting, we'll want to draw them somehow.
# 
# - Singlets still require exactly one bond (unless they've been killed), but it can have
# any valence. This might affect how they're drawn, how they consider forming new bonds
# (in extrude, fuse chunks, depositMode, etc), and how they're written into sim-input mmp files.
#
# - We represent the bond valence as an integer (6 times the actual valence), since we don't
# want to worry about roundoff errors when summing and comparing valences. (Nor to pay the speed
# penalty for using exactly summable python objects that pretend to have the correct numeric value.)
#
# An example of what we don't want to have to worry about:
#
#   >>> 1/2.0 + 1/3.0 + 1/6.0
#   0.99999999999999989
#   >>> _ >= 1.0
#   False
#
# We do guarantee to all code using these bond-valence constants that they can be subtracted
# and compared as numbers -- i.e. that they are "proportional" to the numeric valence.
# Some operations transiently create bonds with unsupported values of valence, especially bonds
# to singlets, and this is later cleaned up by the involved atoms when they update their bonding
# patterns, before those bonds are ever drawn. Except for bugs or perhaps during debugging,
# only standard-valence bonds will ever be drawn, or saved in files, or seen by most code.

# ==

# end
