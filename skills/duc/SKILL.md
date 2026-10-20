---
name: duc
description: "Use this skill whenever a DUC drawing (`.duc` file) needs to be read, written, searched, created, inspected, or manipulated programmatically with the Python `ducpy` library. This includes constructing elements, styles, layers, blocks, and states with fluent builders; querying the relational schema through `DucSQL`; streaming external-file or version payloads; and validating coordinate placement or drawing relationships."
---

# DUC Core Canvas Library Skill

The `ducpy` Python library provides a fast, developer-friendly interface to read, write, search, and manipulate `.duc` project-state files. Under the hood, a current `.duc` file is a **gzip-compressed SQLite database**.

This skill deliberately stays compact. Detailed API signatures and examples belong in the versioned documentation routes below, where they can remain synchronized with the implementation.

---

## `llms.txt` Documentation Routes & Source-of-Truth

`llms.txt` serves as a structured map to direct agents to the most relevant documentation pages. Agents must retrieve relevant linked pages for RAG rather than relying solely on the index file.

### Recommended Source Routing

- **Orchestrator**: `https://duc.ducflair.com/llms.txt`
  - Use for: `.duc` concepts, element categories, coordinate placement, document structure, serialization, state and revision concepts, SQL schema guidance, and deciding which library is required.
- **Generator, Inspector, and Critic**: `https://ducflair.github.io/duc/reference/python/llms.txt`
  - Use for: actual builder methods, method chaining order, parsing and serialization contracts, mutation functions, element classes, model-element code, and runnable examples.
  - Use the maintained `ducpy` examples at `https://ducflair.github.io/duc/reference/python/examples.html` as task scaffolds for element creation, mutation, external files, SQL, serialization, and parsing. Adapt the closest example only after confirming it matches the installed version.
  - *Crucial for preventing invalid method calls, incorrect builder stages, and stale argument or return-value assumptions.*

### Documentation Search

When the relevant documentation page is unknown, search the docs with a GET request:

```bash
curl -sG 'https://duc.ducflair.com/api/search' --data-urlencode 'query=<search terms>'
```

The endpoint returns a JSON array of matching pages and snippets with their `url`. Use it to identify the most relevant result, then open and read that page for the full context; do not treat the search snippet as the complete documentation.

**Direct Markdown Output**:
```bash
# Fetch clean markdown directly example:
curl -s 'https://duc.ducflair.com/docs/concepts/architecture'
```

### Source-of-Truth Hierarchy

Agents must adhere strictly to this priority order:

1. **Runtime introspection of the installed `ducpy` package**
2. **Documentation matching the installed `ducpy` version**
3. **`ducpy` `llms.txt` and linked API pages** (`https://ducflair.github.io/duc/reference/python/llms.txt`)
4. **General DUC documentation** (`https://duc.ducflair.com/llms.txt`)
5. **Existing examples**

> [!IMPORTANT]
> **Runtime Introspection & Verification Rule**
> Runtime introspection remains #1 because remote documentation can describe a different release from the installed package.
> **Rule**: *Never invent a `ducpy` method, parameter, return type, schema column, or builder stage. Retrieve the version-matched reference before generating implementation code.*

---

## Key Design & Code Standards

* **Coordinate System & Units**: `x` and `y` are the element's top-left canvas position. Positive X extends rightward and positive Y extends downward. Linear, arrow, and freedraw points are local to that element origin. Angles are radians, and coordinates and dimensions use the element's declared scope.
* **Current File I/O Contract**: `parse_duc()` accepts a filesystem path and returns recursively wrapped `DucData` dictionaries with flattened snake_case fields. `serialize_duc()` writes a `.duc` file and returns its path; it does not return drawing bytes.
* **In-Place Mutation**: Use `duc.mutate_element()` for builder-created `ElementWrapper` or dataclass objects. Parsed `DucData` elements are dictionaries and should be edited through their existing fields. Never destroy and recreate an element merely to update it, because doing so can lose IDs, memberships, bindings, and other relationships.
* **Binding Preservation**: Preserve existing element IDs, `bound_elements`, group/region/block memberships, `frame_id`, `layer_id`, and instance relationships during edits.
* **Strict Builder Methods**: Methods are stage-specific. Confirm the active builder class and installed-version signature before invocation.
* **Styling Elements (Default Fill & Stroke)**: When generating 2D CAD elements, always explicitly define styles with a default fill (background) or stroke; do not assume they are applied automatically. Refer to [Styling Elements](https://duc.ducflair.com/docs/guidelines/styling-elements) for constructing ordered `backgrounds` and `strokes` arrays using `duc.create_simple_styles`.
* **No Duplicated API Reference**: Do not add volatile builder examples, serialization snippets, or schema catalogs to this skill. Improve the corresponding Duc documentation instead so `llms.txt` remains the maintained source.

---

## Additional Adapter References

The general DUC and `ducpy` routes above remain the primary sources. Use these versioned adapter references when a task targets another DUC interface:

- **SQL schema**: `https://ducflair.github.io/duc/reference/sql/`
- **Rust (`duc`)**: `https://ducflair.github.io/duc/reference/rust/duc/`
- **TypeScript / JavaScript (`ducjs`)**: `https://ducflair.github.io/duc/reference/typescript/`
- **PDF (`ducpdf`)**: `https://ducflair.github.io/duc/reference/pdf/`
- **SVG (`ducsvg`)**: `https://ducflair.github.io/duc/reference/svg`
