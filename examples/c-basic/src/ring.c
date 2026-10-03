/* SPDX-FileCopyrightText: 2026 cpdocs developers */
/* SPDX-License-Identifier: Apache-2.0 */
#include "ring/ring.h"

ring_status ring_push(ring* buffer, unsigned char value) {
    if (buffer->size == buffer->capacity) {
        return RING_FULL;
    }
    buffer->data[buffer->size++] = value;
    return RING_OK;
}
