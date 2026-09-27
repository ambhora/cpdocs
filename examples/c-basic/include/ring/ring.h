/* SPDX-FileCopyrightText: 2026 cpdocs developers */
/* SPDX-License-Identifier: Apache-2.0 */
#ifndef RING_RING_H
#define RING_RING_H

#include <stddef.h>

/// Capacity used when none is given.
#define RING_DEFAULT_CAPACITY 64

/// Outcome of a ring operation.
typedef enum ring_status {
    /// The operation succeeded.
    RING_OK = 0,
    /// The ring is full.
    RING_FULL = 1,
} ring_status;

/// A fixed-capacity ring buffer of bytes.
typedef struct ring {
    /// Storage owned by the caller.
    unsigned char* data;
    /// Number of bytes the storage holds.
    size_t capacity;
    /// Number of bytes currently stored.
    size_t size;
} ring;

/// Append one byte to the ring.
ring_status ring_push(ring* buffer, unsigned char value);

#endif
