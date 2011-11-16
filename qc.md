How to Serialize Device State with QC
======================================

This document describes how to implement save/restore of a device in QEMU using
the QC IDL compiler.  The QC IDL compiler makes it easier to support live
migration in devices by converging the serialization description with the
device type declaration.  It has the following features:

 1. Single description of device state and how to serialize

 2. Fully inclusive serialization description--fields that aren't serialized
    are explicitly marked as such including the reason why.

 3. Optimized for the common case.  Even without any special annotations,
    many devices will Just Work out of the box.

 4. Build time schema definition.  Since QC runs at build time, we have full
    access to the schema during the build which means we can fail the build if
    the schema breaks.

For the rest, of the document, the following simple device will be used as an
example.

    typedef struct SerialDevice {
        SysBusDevice parent;
    
        uint8_t thr;            // transmit holding register
        uint8_t lsr;            // line status register
        uint8_t ier;            // interrupt enable register
    
        int int_pending;        // whether we have a pending queued interrupt
        CharDriverState *chr;   // backend
    } SerialDevice;

Getting Started
---------------

The first step is to move your device struct definition to a header file.  This
header file should only contain the struct definition and any preprocessor
declarations you need to define the structure.  This header file will act as
the source for the QC IDL compiler.

Do not include any function declarations in this header file as QC does not
understand function declarations.

Determining What State Gets Saved
---------------------------------

By default, QC saves every field in a structure it sees.  This provides maximum
correctness by default.  However, device structures generally contain state
that reflects state that is in someway duplicated or not guest visible.  This
more often that not reflects design implementation details.

Since design implementation details change over time, saving this state makes
compatibility hard to maintain since it would effectively lock down a device's
implementation.

QC allows a device author to suppress certain fields from being saved although
there are very strict rules about when this is allowed and what needs to be done
to ensure that this does not impact correctness.

There are three cases where state can be suppressed: when it is **immutable**,
**derived**, or **broken**.  In addition, QC can decide at run time whether to
suppress a field by assigning it a **default** value.

## Immutable Fields

If a field is only set during device construction, based on parameters passed to
the device's constructor, then there is no need to send save and restore this
value.  We call these fields immutable and we tell QC about this fact by using
a **_immutable** marker.

In our *SerialDevice* example, the *CharDriverState* pointer reflects the host
backend that we use to send serial output to the user.  This is only assigned
during device construction and never changes.  This means we can add an
**_immutable** marker to it:

    typedef struct SerialDevice {
        SysBusDevice parent;
    
        uint8_t thr;            // transmit holding register
        uint8_t lsr;            // line status register
        uint8_t ier;            // interrupt enable register
    
        int int_pending;        // whether we have a pending queued interrupt
        CharDriverState _immutable *chr;
    } SerialDevice;

When reviewing patches that make use of the **_immutable** marker, the following
guidelines should be followed to determine if the marker is being used
correctly.

 1. Check to see if the field is assigned anywhere other than the device
    initialization function.

 2. Check to see if any function is being called that modifies the state of the
    field outside of the initialization function.

It can be subtle whether a field is truly immutable.  A good example is a
*QEMUTimer*.  Timer's will usually have their timeout modified with a call to
*qemu_mod_timer()* even though they are only assigned in the device
initialization function.

If the timer is always modified with a fixed value that is not dependent on
guest state, then the timer is immutable since it's unaffected by the state of
the guest.

On the other hand, if the timer is modified based on guest state (such as a
guest programmed time out), then the timer carries state.  It may be necessary
to save/restore the timer or mark it as **_derived** and work with it
accordingly.

### Derived Fields

If a field is set based on some other field in the device's structure, then its
value is derived.  Since this is effectively duplicate state, we can avoid
sending it and then recompute it when we need to.  Derived state requires a bit
more handling that immutable state.

In our *SerialDevice* example, our *int_pending* flag is really derived from
two pieces of state.  It is set based on whether interrupts are enabled in the
*ier* register and whether there is *THRE* flag is not set in the *lsr*
register.

To mark a field as derived, use the **_derived** marker.  To update our
example, we would do:

    typedef struct SerialDevice {
        SysBusDevice parent;
    
        uint8_t thr;            // transmit holding register
        uint8_t lsr;            // line status register
        uint8_t ier;            // interrupt enable register
    
        int _derived int_pending; // whether we have a pending queued interrupt
        CharDriverState _immutable *chr;
    } SerialDevice;

There is one other critical step needed when marking a field as derived.  A
*post_load* function must be added that updates this field after loading the
rest of the device state.  This function is implemented in the device's source
file, not in the QC header.  Below is an example of what this function may do:

    static void serial_post_load(SerialDevice *s)
    {
        s->int_pending = !(s->lsr & THRE) && (s->ier & INTE);
    }

When reviewing a patch that marks a field as *_derived*, the following criteria
should be used:

 1. Does the device have a post load function?

 2. Does the post load function assign a value to all of the derived fields?

 3. Are there any obvious places where a derived field is holding unique state?

### Broken State

QEMU does migration with a lot of devices today.  When applying this methodology
to these devices, one will quickly discover that there are a lot of fields that
are not being saved today that are not derived or immutable state.

These are all bugs.  It just so happens that these bugs are usually not very
serious.  In many cases, they cause small functionality glitches that so far
have not created any problems.

Consider our *SerialDevice* example.  In QEMU's real *SerialState* device, the
*thr* register is not saved yet we have not marked it immutable or derived.

The *thr* register is a temporary holding register that the next character to
transmit is placed in while we wait for the next baud cycle.  In QEMU, we
emulate a very fast baud rate regardless of what guest programs.  This means
that the contents of the *thr* register only matter for a very small period of
time (measured in microseconds).

The likelihood of a migration converging in that very small period of time when
the *thr* register has a meaningful value is very small.  Moreover, the worst
thing that can happen by not saving this register is that we lose a byte in the
data stream.  Even if this has happened in practice, the chances of someone
noticing this as a bug is pretty small.

Nonetheless, this is a bug and needs to be eventually fixed.  However, it would
be very inconvenient to constantly break migration by fixing all of these bugs
one-by-one.  Instead, QC has a **_broken** marker.  This indicates that a field
is not currently saved, but should be in the future.

The idea behind the broken marker is that we can convert a large number of
devices without breaking migration compatibility, and then institute a flag day
where we go through and remove broken markers en-mass.

Below is an update of our example to reflect our real life serial device:

    typedef struct SerialDevice {
        SysBusDevice parent;
    
        uint8_t _broken thr;    // transmit holding register
        uint8_t lsr;            // line status register
        uint8_t ier;            // interrupt enable register
    
        int _derived int_pending; // whether we have a pending queued interrupt
        CharDriverState _immutable *chr;
    } SerialDevice;

When reviewing the use of the broken marker, the following things should be
considered:

 1. What are the ramifications of not sending this data field?

 2. If the not sending this data field can cause data corruption or very poor
    behavior within the guest, the broken marker is not appropriate to use.

 3. Assigning a default value to a field can also be used to fix a broken field
    without significantly impacting live migration compatibility.

### Default Values

In many cases, a field that gets marked broken was not originally saved because
in the vast majority of the time, the field does not contain a meaningful value.

In the case of our *thr* example, the field usually does not have a meaningful
value.

Instead of always saving the field, QC has another mechanism that allows the
field to be saved only when it has a meaningful value.  This is done using the
**_default()** marker.  The default marker tells QC that if the field currently
has a specific value, do not save the value as part of serialization.

When loading a field, QC will assign the default value to the field before it
tries to load the field.  If the field cannot be loaded, QC will ignore the
error and rely on the default value.

Using default values, we can fix broken fields while also minimizing the cases
where we break live migration compatibility.  The **_default()** marker can be
used in conjunction with the **_broken** marker.  We can extend our example as
follows:

    typedef struct SerialDevice {
        SysBusDevice parent;
    
        
        uint8_t thr _default(0); // transmit holding register
        uint8_t lsr;             // line status register
        uint8_t ier;             // interrupt enable register
    
        int _derived int_pending; // whether we have a pending queued interrupt
        CharDriverState _immutable *chr;
    } SerialDevice;

The following guidelines should be followed when using a default marker:

 1. Is the field set to the default value both during device initialization and
    whenever the field is no longer in use?

 2. If the non-default value is expected to occur often, then consider using the
    **_broken** marker along with the default marker and using a flag day to
    remove the **_broken** marker.

 3. In general, setting default values as the value during device initialization
    is a good idea even if the field was never broken.  This gives us maximum
    flexibility in the long term.

 4. Never change a default value without renaming a field.  The default value is
    part of the device's ABI.

The first guideline is particularly important.  In the case of QEMU's real
*SerialDevice*, it would be necessary to add code to set the *thr* register to
zero after the byte has been successfully transmitted.  Otherwise, it is
unlikely that it would ever contain the default value.

Arrays
------

QC has support for multiple types of arrays.  The following sections describe
the different rules for arrays.

Fixed Sized Arrays
------------------

A fixed sized array has a size that is known at build time.  A typical example
would be:

    struct SerialFIFO {
        uint8_t data[UART_FIFO_LENGTH];
        uint8_t count;
        uint8_t itl;
        uint8_t tail;
        uint8_t head;
    };

In this example, *data* is a fixed sized array.  No special annotation is needed
for QC to marshal this area correctly.  The following guidelines apply to
fixed sized arrays:

 1. The size of the array is part of the device ABI.  It should not change
    without renaming the field.

Variable Sized, Fixed Capacity Arrays
-------------------------------------

Sometimes it's desirable to have a variable sized array.  QC currently supported
variable sized arrays provided that the maximum capacity is fixed and part of
the device structure memory.

A typical example would be a slightly modified version of our above example:

    struct SerialFIFO {
        uint8_t count;
        uint8_t _size_is(count) data[UART_FIFO_LENGTH];
        uint8_t itl;
        uint8_t tail;
        uint8_t head;
    };

In this example, *data* is a variable sized array with a fixed capacity of
*UART_FIFO_LENGTH*.  When we serialize, we want only want to serialize *count*
members.

The ABI implications of capacity are a bit more relaxed with variable sized
arrays.  In general, you can increase or decrease the capacity without breaking
the ABI although you may cause some instances of migration to fail between
versions of QEMU with different capacities.

When reviewing variable sized, fixed capacity arrays, keep the following things
in mind:

 1. The variable size must occur before the array element in the state
    structure.

 2. The capacity can change without breaking the ABI, but care should be used
    when making these types of changes.
