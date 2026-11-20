/** @file
  SerialPortLib.c
  Project R8Q Qualcomm GENI UART Serial Port Driver Library.
  Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)

  Base MMIO: 0x00A90000 (QUP v3 SE12 GENI UART / /dev/ttyHS8)

  Features:
  - Hardware safe probing to detect unclocked/uninitialized controllers.
  - Bounded FIFO polling with automatic timeout fallback.
  - Safe non-blocking operation: UART failure NEVER stalls boot or GOP.

  Copyright (c) 2026, Antigravity Engineering. All rights reserved.
**/

#include <Base.h>
#include <Library/SerialPortLib.h>
#include <Library/IoLib.h>
#include <Library/PcdLib.h>

#define DEFAULT_GENI_UART_BASE      0x00A90000ULL
#define GENI_TX_FIFO_STATUS_OFFSET  0x0800
#define GENI_TX_FIFO_OFFSET         0x0700
#define GENI_RX_FIFO_STATUS_OFFSET  0x0804
#define GENI_RX_FIFO_OFFSET         0x0780
#define GENI_STATUS_OFFSET          0x0040

STATIC BOOLEAN mUartInitialized = FALSE;
STATIC BOOLEAN mUartAvailable   = FALSE;

STATIC
UINT64
GetUartBase (
  VOID
  )
{
  UINT64 Base = PcdGet64 (PcdUartBaseAddress);
  return (Base != 0) ? Base : DEFAULT_GENI_UART_BASE;
}

RETURN_STATUS
EFIAPI
SerialPortInitialize (
  VOID
  )
{
  UINT64 UartBase;
  UINT32 RegVal;

  if (mUartInitialized) {
    return RETURN_SUCCESS;
  }
  mUartInitialized = TRUE;

  UartBase = GetUartBase ();

  // Safe probe: verify if controller MMIO responds without bus error
  // If unclocked or power-gated, reads return 0x0 or 0xFFFFFFFF
  RegVal = MmioRead32 (UartBase + GENI_TX_FIFO_STATUS_OFFSET);
  if (RegVal == 0xFFFFFFFF || RegVal == 0x00000000) {
    // Controller is unclocked or disabled in production bootloader
    mUartAvailable = FALSE;
  } else {
    mUartAvailable = TRUE;
  }

  return RETURN_SUCCESS;
}

UINTN
EFIAPI
SerialPortWrite (
  IN UINT8     *Buffer,
  IN UINTN     NumberOfBytes
  )
{
  UINT64 UartBase;
  UINTN  Index;
  UINT32 Timeout;

  if (Buffer == NULL || NumberOfBytes == 0) {
    return 0;
  }

  if (!mUartInitialized) {
    SerialPortInitialize ();
  }

  if (!mUartAvailable) {
    // Non-blocking bypass: do not stall firmware boot or console
    return NumberOfBytes;
  }

  UartBase = GetUartBase ();

  for (Index = 0; Index < NumberOfBytes; Index++) {
    // If newline, output carriage return first
    if (Buffer[Index] == '\n') {
      Timeout = 10000;
      while ((MmioRead32 (UartBase + GENI_TX_FIFO_STATUS_OFFSET) & 0x7F) >= 60 && --Timeout > 0) {
        // Bounded wait for FIFO headroom
      }
      if (Timeout == 0) {
        mUartAvailable = FALSE;
        return Index;
      }
      MmioWrite32 (UartBase + GENI_TX_FIFO_OFFSET, (UINT32)'\r');
    }

    Timeout = 10000;
    while ((MmioRead32 (UartBase + GENI_TX_FIFO_STATUS_OFFSET) & 0x7F) >= 60 && --Timeout > 0) {
      // Bounded wait for FIFO headroom
    }
    if (Timeout == 0) {
      mUartAvailable = FALSE;
      return Index;
    }
    MmioWrite32 (UartBase + GENI_TX_FIFO_OFFSET, (UINT32)Buffer[Index]);
  }

  return NumberOfBytes;
}

UINTN
EFIAPI
SerialPortRead (
  OUT UINT8     *Buffer,
  IN  UINTN     NumberOfBytes
  )
{
  UINT64 UartBase;
  UINTN  Count = 0;

  if (Buffer == NULL || NumberOfBytes == 0) {
    return 0;
  }

  if (!mUartInitialized) {
    SerialPortInitialize ();
  }

  if (!mUartAvailable) {
    return 0;
  }

  UartBase = GetUartBase ();

  while (Count < NumberOfBytes) {
    if ((MmioRead32 (UartBase + GENI_RX_FIFO_STATUS_OFFSET) & 0x7F) > 0) {
      Buffer[Count++] = (UINT8)(MmioRead32 (UartBase + GENI_RX_FIFO_OFFSET) & 0xFF);
    } else {
      break;
    }
  }

  return Count;
}

BOOLEAN
EFIAPI
SerialPortPoll (
  VOID
  )
{
  UINT64 UartBase;

  if (!mUartInitialized) {
    SerialPortInitialize ();
  }

  if (!mUartAvailable) {
    return FALSE;
  }

  UartBase = GetUartBase ();
  return ((MmioRead32 (UartBase + GENI_RX_FIFO_STATUS_OFFSET) & 0x7F) > 0);
}

RETURN_STATUS
EFIAPI
SerialPortSetControl (
  IN UINT32 Control
  )
{
  return RETURN_SUCCESS;
}

RETURN_STATUS
EFIAPI
SerialPortGetControl (
  OUT UINT32 *Control
  )
{
  if (Control == NULL) {
    return RETURN_INVALID_PARAMETER;
  }
  *Control = EFI_SERIAL_DATA_TERMINAL_READY | EFI_SERIAL_REQUEST_TO_SEND;
  return RETURN_SUCCESS;
}

RETURN_STATUS
EFIAPI
SerialPortSetAttributes (
  IN OUT UINT64             *BaudRate,
  IN OUT UINT32             *ReceiveFifoDepth,
  IN OUT UINT32             *Timeout,
  IN OUT EFI_PARITY_TYPE    *Parity,
  IN OUT UINT8              *DataBits,
  IN OUT EFI_STOP_BITS_TYPE *StopBits
  )
{
  return RETURN_SUCCESS;
}
