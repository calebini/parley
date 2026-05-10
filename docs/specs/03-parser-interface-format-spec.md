# Parser Interface and Format Specification

## 1. Scope

This specification defines the parser abstraction, normalized representation, initial iOS `.strings` behavior, Android XML behavior, escaping rules, comment handling, duplicate-key handling, diagnostics, and write-back guarantees.

It depends on:

- [Project Artifact Schema Specification](02-project-artifact-schema-spec.md)
- [Placeholder and Token Integrity Specification](04-placeholder-token-integrity-spec.md)
- [Validation and Error Taxonomy Specification](07-validation-error-taxonomy-spec.md)

## 2. Parser IDs and Supported Formats

Required v1 parser IDs:

| Parser ID | Format | File types |
| --- | --- | --- |
| `ios_strings.v1` | `ios_strings` | `.strings` |
| `android_xml.v1` | `android_xml` | Android `strings.xml` resource files |

## 3. Parser Interface

```python
class LocalizationParser(Protocol):
    parser_id: str
    format: str

    def supports(self, path: Path, declared_format: str | None = None) -> bool: ...
    def parse(self, path: Path, locale: str) -> ParsedLocalizationFile: ...
    def write(
        self,
        source: ParsedLocalizationFile,
        updates: Sequence[LocalizationEntryUpdate],
        destination: Path,
        options: WriteOptions,
    ) -> WriteResult: ...
```

Parser implementations MUST NOT call translation or semantic providers.

## 4. Normalized Representation

### 4.1 `ParsedLocalizationFile`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `schema_version` | string | yes | MUST be `"1.0"`. |
| `parser_id` | string | yes | Parser adapter ID. |
| `format` | enum | yes | `ios_strings` or `android_xml`. |
| `source_path` | path | yes | Source file path. |
| `locale` | Locale | yes | File locale. |
| `file_hash` | Hash | yes | Hash of normalized entries and parser metadata. |
| `entries` | array | yes | Normalized entries in source order. |
| `diagnostics` | array | yes | Parser diagnostics. |
| `metadata` | object | yes | File-level parser metadata. |

### 4.2 `LocalizationEntry`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `key` | string | yes | Localization key. |
| `value` | string | yes | Localized string value. |
| `locale` | Locale | yes | Entry locale. |
| `format` | enum | yes | Source format. |
| `source_path` | path | yes | Source file path. |
| `source_span` | object/null | yes | Line/column range when available. |
| `metadata` | object | yes | Format-specific metadata. |
| `comments` | array | yes | Associated comments. |
| `placeholders` | array | yes | Placeholder tokens. |
| `placeholder_signature` | string | yes | Normalized placeholder signature. |
| `content_hash` | Hash | yes | Entry content hash. |

Entry order MUST match source file order after parser-specific normalization.

### 4.3 Parser Diagnostic

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `category` | finding category enum | yes | Usually `parser_syntax` or `localization_syntax`. |
| `severity` | severity enum | yes | Shared severity. |
| `message` | string | yes | Human-readable diagnostic. |
| `key` | string/null | yes | Key when known. |
| `source_span` | object/null | yes | File location when known. |

Fatal parse failures MUST produce exit code `3`. Recoverable parser diagnostics MUST be represented as validation findings.

## 5. iOS `.strings` Behavior

### 5.1 Accepted Grammar

The v1 parser MUST support Apple `.strings` entries of this form:

```text
"key" = "value";
```

It MUST support:

- Double-quoted keys.
- Double-quoted values.
- C-style block comments `/* ... */`.
- Line comments `// ...`.
- Escaped quotes `\"`.
- Escaped backslash `\\`.
- Common escaped sequences such as `\n`, `\r`, and `\t`.
- Unicode escape sequences present in existing files.

### 5.2 Comments

Comments immediately preceding an entry MUST be associated with that entry in `comments`.

Write-back SHOULD preserve associated comments for unchanged and updated entries.

### 5.3 Duplicate Keys

Duplicate keys MUST produce a `structural` finding with severity `blocking`.

The parser MUST keep all duplicate entries in `entries` and mark duplicate metadata:

```json
{"duplicate_index": 2, "first_occurrence_line": 10}
```

Write-back MUST fail with exit code `3` if duplicate keys remain unresolved in a destination file.

### 5.4 Write-Back

For existing `.strings` files, write-back MUST:

- Preserve source order for existing keys.
- Preserve comments where possible.
- Preserve quote escaping rules.
- Update only changed values.
- Append newly generated keys at the end unless an ordering policy is supplied.

## 6. Android XML Behavior

### 6.1 Supported Resources

The v1 parser MUST support:

```xml
<resources>
  <string name="key">Value</string>
</resources>
```

The v1 parser MAY parse but does not need to fully write:

- `string-array`
- `plurals`

If unsupported resources are present, the parser MUST emit `info` diagnostics and preserve them during write-back when possible.

### 6.2 XML Escaping

The parser MUST decode XML entities for normalized `value`:

- `&amp;`
- `&lt;`
- `&gt;`
- `&quot;`
- `&apos;`

Write-back MUST re-escape XML-sensitive characters.

### 6.3 Attributes

The parser MUST preserve:

- `name`
- `translatable`
- `formatted`
- Namespaced attributes when present.

Entries with `translatable="false"` MUST be parsed with metadata:

```json
{"translatable": false}
```

Translation workflows MUST skip entries where `translatable` is false unless explicitly overridden.

### 6.4 Duplicate Keys

Duplicate `<string name="...">` entries MUST produce a `structural` finding with severity `blocking`.

### 6.5 Write-Back

For Android XML files, write-back MUST:

- Preserve non-string resources where possible.
- Preserve resource order for existing keys.
- Preserve comments where possible.
- Update only changed string text.
- Escape values according to XML rules.
- Keep `translatable="false"` entries unchanged.

## 7. Parser Metadata

Parser metadata SHOULD include:

- Encoding.
- Line ending style.
- Original file hash.
- Parser version.
- Unsupported resource counts.

## 8. WriteResult

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `written` | boolean | yes | Whether destination was written. |
| `destination` | path | yes | Destination path. |
| `updated_keys` | array | yes | Keys updated. |
| `added_keys` | array | yes | Keys added. |
| `skipped_keys` | array | yes | Keys skipped and reason. |
| `diagnostics` | array | yes | Write diagnostics. |

