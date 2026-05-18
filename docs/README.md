# GaussDB Documentation Notes

This directory contains the GaussDB-specific material added for the Mem0 vector store integration.

## Main documents

- [Requirements Analysis](gaussdb-mem0-requirements-analysis.md)
- [Technical Design](gaussdb-mem0-technical-design.md)
- [User Guide](gaussdb-mem0-user-guide.md)

## Preview locally

Install the Mintlify CLI:

```bash
npm i -g mintlify
```

Run the docs site from the `docs/` directory:

```bash
mintlify dev
```

## Scope

These GaussDB documents are intended to complement the standard Mem0 component documentation. They focus on:

- provider-specific design choices
- deployment and operational guidance
- centralized versus distributed behavior
- filter semantics and known boundaries

For public-facing integration docs, also see:

- [GaussDB integration page](components/vectordbs/dbs/gaussdb.mdx)
