# Placeholder and Token Integrity Specification

## 1. Scope

This specification defines placeholder/token grammar, normalized token signatures, equivalence rules, ICU handling, markup handling, reorder rules, and validation severity mapping.

It depends on:

- [Parser Interface and Format Specification](03-parser-interface-format-spec.md)
- [Validation and Error Taxonomy Specification](07-validation-error-taxonomy-spec.md)

## 2. Placeholder Token Model

`PlaceholderToken` fields:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | string | yes | Stable token ID within an entry. |
| `kind` | enum | yes | Token kind. |
| `raw` | string | yes | Raw token text. |
| `name` | string/null | yes | Variable or argument name when present. |
| `position` | integer/null | yes | Positional index when present. |
| `format_type` | string/null | yes | Format type such as `d`, `s`, `@`, or ICU type. |
| `span` | object/null | yes | Character span in normalized value. |
| `reorderable` | boolean | yes | Whether valid translation may reorder token. |
| `protected` | boolean | yes | Whether token raw text must be preserved exactly. |

Token kinds:

- `interpolation_variable`
- `printf_format`
- `icu_argument`
- `icu_message`
- `templating_expression`
- `markup_tag`
- `positional_placeholder`

## 3. Supported Token Grammars

### 3.1 Interpolation Variables

Examples:

- `{name}`
- `{count}`

Pattern:

```text
\{[A-Za-z_][A-Za-z0-9_.-]*\}
```

### 3.2 Printf Format Tokens

Examples:

- `%d`
- `%s`
- `%@`
- `%1$d`
- `%.2f`

The parser MUST recognize common printf placeholders including optional positional index, flags, width, precision, and type.

### 3.3 Templating Expressions

Examples:

- `{{amount}}`
- `{{ user.name }}`

Templating expressions are protected by default. Inner whitespace differences are normalized for equivalence.

### 3.4 ICU Messages

Examples:

- `{count, plural, one {# item} other {# items}}`
- `{gender, select, male {He} female {She} other {They}}`

The placeholder engine MUST detect ICU argument name, ICU type, and branch labels.

ICU parsing may initially be conservative. If an entry appears to contain ICU syntax but cannot be parsed safely, emit a `placeholder_integrity` finding with severity `blocking`.

### 3.5 Markup Tags

Examples:

- `<b>Continue</b>`
- `<a href="%@">Terms</a>`

Supported v1 markup detection covers simple XML/HTML-like tags. Tags are protected by default.

## 4. Placeholder Signature

The placeholder signature is a stable string derived from ordered normalized tokens:

```text
kind:name:position:format_type:protected
```

Tokens are joined with `|`.

Example:

```text
interpolation_variable:name:::true|printf_format::1:d:true
```

For reorderable named tokens, order-sensitive validation MAY compare as a multiset. For positional and markup tokens, order is significant by default.

## 5. Equivalence Rules

Tokens are equivalent when:

- `kind` matches.
- `name` matches after grammar-specific normalization.
- `position` matches when present.
- `format_type` matches when present.
- Protected raw text is identical when `protected` is true.

Examples:

- `{name}` is equivalent to `{name}`.
- `{{ amount }}` is equivalent to `{{amount}}`.
- `%d` is not equivalent to `%@`.
- `%1$d` is not equivalent to `%2$d`.
- `<b>` is not equivalent to `<strong>` in v1.

## 6. Reorder Rules

Reordering is valid only when one of these is true:

- Tokens are named and `reorderable` is true.
- Tokens are explicitly positional and the target preserves positions.
- A format-specific rule marks the token sequence as reorder-safe.

Reordering is invalid by default for:

- Markup open/close tag ordering.
- Non-positional printf tokens.
- ICU branch structure.

## 7. Validation Findings

All placeholder issues MUST use category `placeholder_integrity`.

Severity mapping:

| Condition | Severity |
| --- | --- |
| Missing placeholder in target | `blocking` |
| Extra placeholder in target | `error` |
| Placeholder type mismatch | `blocking` |
| Malformed placeholder syntax | `blocking` |
| Protected token translated or altered | `blocking` |
| Invalid reorder | `error` |
| ICU parse uncertainty | `blocking` |
| Markup imbalance | `blocking` |
| Whitespace-only templating normalization difference | `info` |

## 8. Translation Protection

Before provider translation, the translation workflow SHOULD replace protected tokens with stable sentinels:

```text
__PARLEY_TOKEN_0__
```

After provider output, sentinels MUST be restored and placeholder validation MUST run. Any unresolved sentinel is a `placeholder_integrity` finding with severity `blocking`.
