Migration in QEMU is just object serialization.  A simple implementation would
just save every field that's reachable in the structure definition for a device.
This would be obviously correct but it would send a lot of information that is
really just implementation details in QEMU.  This would make live migration
compatibility nearly impossible.

To support compatibility, we add annotations to our structure definitions that
prevents the state from being sent over the wire.  This document describes
what these annotations are and when they should be used.

Immutable State
---------------

Immutable state are fields that do not change state after the device has been
initialized.  To mark a field as immutable, use the **_immutable** marker.  You
can tell if a field is really immutable by searching for any code that sets or
modifies the field.  If it occurs outside the device init function, then the
field is not immutable.

    uint32_t _immutable iobase;

Derived State
-------------

Derived state are fields who's values are based on other fields.  These fields
usually exist simply because it's more convienent to duplicate the state.  You
can determine if a field is derived by looking for a post_load() hook in the
migration handling code.  Any derived field should be assigned in the
post_load() function.  To mark a field as derived, use the **_derived** marker.

    uint32_t _derived carry_flag;

Broken State
------------

An all too common case is that certain fields are not currently serialized but
should be.  Often, we get away with this by causing subtle guest visible changes
in behavior that don't cause obvious breaks in functionality.

In other cases, these states are almost always fixed as a certain default value
as they represent very transient device state.

In both cases, this is a bug that needs to be fixed.  Usually the fix is
simply removing the marker to send the field.  It's convenient to use a broken
marker though so that a large number of devices can have the markers removed
all at the same time.  This reduces the frequency of live migration breaks.

To mark a field as broken, use the **_broken** marker.

    int _broken pending_interrupt;

Default Values
--------------

Another trick in reducing the amount of state sent is to pick a default value
for a field.  This value will be set before incoming migration is received.  It
is often convenient to set this value to whatever the default value would be
after reset.  During live migration, if a field is detected to be at it's
default value, the field will simply not be sent.  To assign a default value
to a field, use the **_default(V)** marker with *V* set to be a literal value.

Very often, default values can be set to avoid breakage when removing the
**_broken** marker from a field.

    int pending_interrupt _default(0);
