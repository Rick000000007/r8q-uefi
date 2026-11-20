/** @file
  SerialPortLib.c
  Project R8Q Qualcomm GENI UART Serial Port Driver Library.
  Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)

  Base MMIO: 0x00988000 (QUP GENI UART)

  Copyright (c) 2026, Antigravity Engineering. All rights reserved.
**/

#include <Base.h>
#include <Library/SerialPortLib.h>
#include <Library/IoLib.h>
#include <Library/PcdLib.h>

#define GENI_UART_BASE              0x00988000ULL
#define GENI_TX_FIFO_STATUS         (GENI_UART_BASE + 0x0800)
#define GENI_TX_FIFO                (GENI_UART_BASE + 0x0700)
#define GENI_RX_FIFO_STATUS         (GENI_UART_BASE + 0x0804)
#define GENI_RX_FIFO                (GENI_UART_BASE + 0x0780)

RETURN_STATUS
EFIAPI
SerialPortInitialize (
  VOID
  )
{
  // UART clock and baud are pre-configured by AOP/XBL
  return RETURN_SUCCESS;
}

UINTN
EFIAPI
SerialPortWrite (
  IN UINT8     *Buffer,
  IN UINTN     NumberOfBytes
  )
{
  UINTN Index;

  for (Index = 0; Index < NumberOfBytes; Index++) {
    // If newline, output carriage return first
    if (Buffer[Index] == '\n') {
      while ((MmioRead32 (GENI_TX_FIFO_STATUS) & 0x7F) >= 60) {
        // Wait for FIFO headroom
      }
      MmioWrite32 (GENI_TX_FIFO, (UINT32)'\r');
    }

    while ((MmioRead32 (GENI_TX_FIFO_STATUS) & 0x7F) >= 60) {
      // Wait for FIFO headroom
    }
    MmioWrite32 (GENI_TX_FIFO, (UINT32)Buffer[Index]);
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
  UINTN Count = 0;

  while (Count < NumberOfBytes) {
    if ((MmioRead32 (GENI_RX_FIFO_STATUS) & 0x7F) > 0) {
      Buffer[Count++] = (UINT8)(MmioRead32 (GENI_RX_FIFO) & 0xFF);
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
  return ((MmioRead32 (GENI_RX_FIFO_STATUS) & 0x7F) > 0);
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
