typedef struct SerialFIFO {
    uint8_t data[UART_FIFO_LENGTH];
    uint8_t count;
    uint8_t itl;                        /* Interrupt Trigger Level */
    uint8_t tail;
    uint8_t head;
} SerialFIFO;

struct SerialState {
    uint16_t divider;
    uint8_t rbr; /* receive register */
    uint8_t _derived thr; /* transmit holding register */
    uint8_t _derived tsr; /* transmit shift register */
    uint8_t ier;
    uint8_t iir; /* read only */
    uint8_t lcr;
    uint8_t mcr;
    uint8_t lsr; /* read only */
    uint8_t msr; /* read only */
    uint8_t scr;
    uint8_t _derived fcr;
    uint8_t fcr_vmstate; /* we can't write directly this value
                            it has side effects */
    /* NOTE: this hidden state is necessary for tx irq generation as
       it can be reset while reading iir */
    int thr_ipending _default(0);
    qemu_irq _immutable irq;
    CharDriverState _immutable *chr;
    int _derived last_break_enable;
    int _immutable it_shift;
    int _immutable baudbase;
    int _immutable tsr_retry;

    uint64_t _derived last_xmit_ts;              /* Time when the last byte was successfully sent out of the tsr */
    SerialFIFO _derived recv_fifo;
    SerialFIFO _derived xmit_fifo;

    struct QEMUTimer _derived *fifo_timeout_timer;
    int timeout_ipending _default(0);                   /* timeout interrupt pending state */
    struct QEMUTimer _derived *transmit_timer;


    uint64_t _immutable char_transmit_time;               /* time to transmit a char in ticks*/
    int _derived poll_msl;

    struct QEMUTimer _derived *modem_status_poll;
    MemoryRegion _immutable io;
};

