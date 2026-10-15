// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 cpdocs developers
#pragma once
#ifdef USE_CUDA
/// Active backend.
#define DICE_BACKEND "cuda"
namespace dice { struct cuda_view {}; void foo(cuda_view); [[nodiscard]] int backend_name(); }
#else
/// Active backend.
#define DICE_BACKEND "cpu"
namespace dice { struct cpu_view {}; void foo(cpu_view); [[nodiscard]] int backend_name(); }
#endif
class visible { public: void yes(); private: void no(); };
