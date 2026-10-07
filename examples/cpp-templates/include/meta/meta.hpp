// SPDX-FileCopyrightText: 2026 cpdocs developers
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <concepts>
#include <cstddef>
#include <type_traits>
#include <utility>

/// Generic building blocks: templates, specializations, concepts and SFINAE.
namespace meta {

/// Types that support `+` and yield the same type.
template <typename T>
concept addable = requires(T a, T b) {
    { a + b } -> std::same_as<T>;
};

/// Arithmetic types, integral or floating point.
template <typename T>
concept arithmetic = std::integral<T> || std::floating_point<T>;

/// A fixed-size vector.
///
/// @tparam T Element type.
/// @tparam N Number of elements.
template <typename T, std::size_t N>
struct vec {
    /// Elements.
    T data[N];

    /// Number of elements.
    static constexpr std::size_t size() noexcept { return N; }

    /// Element access.
    constexpr T& operator[](std::size_t index) noexcept { return data[index]; }
};

/// Partial specialization for empty vectors.
template <typename T>
struct vec<T, 0> {
    /// Always zero.
    static constexpr std::size_t size() noexcept { return 0; }
};

/// Describes how a type is stored on disk.
template <typename T>
struct storage_traits {
    /// Bytes used on disk.
    static constexpr std::size_t bytes = sizeof(T);
};

/// Full specialization: booleans are stored as one byte.
template <>
struct storage_traits<bool> {
    /// Bytes used on disk.
    static constexpr std::size_t bytes = 1;
};

/// Sum of two values, constrained by a concept.
template <addable T>
constexpr T sum(T a, T b) {
    return a + b;
}

/// Scale a value; the requires clause restricts it to arithmetic types.
template <typename T>
    requires arithmetic<T>
constexpr T scale(T value, T factor) {
    return value * factor;
}

/// Abbreviated function template with a constrained placeholder.
constexpr auto twice(arithmetic auto value) { return value + value; }

/// Integer square root, enabled only for integral types (SFINAE on the return type).
template <typename T>
std::enable_if_t<std::is_integral_v<T>, T> isqrt(T value);

/// Floating-point square root, enabled through a defaulted template parameter (SFINAE).
template <typename T, typename = std::enable_if_t<std::is_floating_point_v<T>>>
T fsqrt(T value);

/// Alias template for a vector of three elements.
template <typename T>
using vec3 = vec<T, 3>;

/// Variable template: whether a type is stored in a single byte.
template <typename T>
inline constexpr bool is_byte_sized = storage_traits<T>::bytes == 1;

/// Heterogeneous tuple of values.
template <typename... Ts>
struct pack {
    /// Number of types in the pack.
    static constexpr std::size_t count = sizeof...(Ts);
};

/// Build a pack from values; a variadic function template.
template <typename... Ts>
constexpr pack<std::decay_t<Ts>...> make_pack(Ts&&... values) noexcept;

/// Base class of the curiously recurring template pattern.
template <typename Derived>
struct counter {
    /// Number of instances of `Derived` created so far.
    static std::size_t created() noexcept;
};

/// Applies a template template parameter to `int`.
template <template <typename> class F>
using apply_int = F<int>;

/// A value paired with a label; demonstrates class template argument deduction.
template <typename T>
struct labelled {
    /// The value.
    T value;
    /// Its label.
    char const* label;
};

/// Deduction guide: `labelled{3.0, "x"}` is a `labelled<double>`.
template <typename T>
labelled(T, char const*) -> labelled<T>;

} // namespace meta
