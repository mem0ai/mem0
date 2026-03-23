function loadOptionalDepsModuleWithMockedRequire(
  mockedRequire: (name: string) => any,
): typeof import("../utils/optional-deps") {
  jest.resetModules();
  jest.doMock("module", () => {
    const actual = jest.requireActual("module");
    return {
      ...actual,
      createRequire: () => mockedRequire,
    };
  });

  let loadedModule: typeof import("../utils/optional-deps");
  jest.isolateModules(() => {
    loadedModule = require("../utils/optional-deps");
  });

  jest.dontMock("module");
  jest.resetModules();
  return loadedModule!;
}

function missingModuleError(moduleName: string): Error & { code: string } {
  const error = new Error(`Cannot find module '${moduleName}'`) as Error & {
    code: string;
  };
  error.code = "MODULE_NOT_FOUND";
  return error;
}

describe("optional dependency loader utility", () => {
  it("resolves default export", () => {
    const { loadOptionalDependency } = loadOptionalDepsModuleWithMockedRequire(
      (name) => {
        if (name === "test-default-package") {
          return { default: "DEFAULT_VALUE" };
        }
        throw missingModuleError(name);
      },
    );

    expect(loadOptionalDependency("test-default-package", "test usage")).toBe(
      "DEFAULT_VALUE",
    );
  });

  it("resolves named export from top-level module object", () => {
    const { loadOptionalDependency } = loadOptionalDepsModuleWithMockedRequire(
      (name) => {
        if (name === "test-named-package") {
          return { createClient: "NAMED_VALUE" };
        }
        throw missingModuleError(name);
      },
    );

    expect(
      loadOptionalDependency(
        "test-named-package",
        "test usage",
        "createClient",
      ),
    ).toBe("NAMED_VALUE");
  });

  it("resolves named export from nested default object", () => {
    const { loadOptionalDependency } = loadOptionalDepsModuleWithMockedRequire(
      (name) => {
        if (name === "test-nested-default-package") {
          return {
            default: { SearchClient: "SEARCH_CLIENT_CTOR" },
          };
        }
        throw missingModuleError(name);
      },
    );

    expect(
      loadOptionalDependency(
        "test-nested-default-package",
        "test usage",
        "SearchClient",
      ),
    ).toBe("SEARCH_CLIENT_CTOR");
  });

  it("maps MODULE_NOT_FOUND to friendly install hint for known package", () => {
    const { loadOptionalDependency } = loadOptionalDepsModuleWithMockedRequire(
      (name) => {
        throw missingModuleError(name);
      },
    );

    expect(() =>
      loadOptionalDependency("better-sqlite3", "sqlite history store"),
    ).toThrow(
      "Install optional dependency 'better-sqlite3' to use sqlite history store. Try: pnpm add better-sqlite3",
    );
  });

  it("falls back to generic install hint for unknown package", () => {
    const { loadOptionalDependency } = loadOptionalDepsModuleWithMockedRequire(
      (name) => {
        throw missingModuleError(name);
      },
    );

    expect(() =>
      loadOptionalDependency("unknown-optional-package", "custom provider"),
    ).toThrow("Try: pnpm add unknown-optional-package");
  });

  it("preserves non-MODULE_NOT_FOUND errors", () => {
    const { loadOptionalDependency } = loadOptionalDepsModuleWithMockedRequire(
      () => {
        throw new Error("unexpected runtime failure");
      },
    );

    expect(() =>
      loadOptionalDependency("better-sqlite3", "sqlite history store"),
    ).toThrow("unexpected runtime failure");
  });

  it("throws clear error when expected export is missing", () => {
    const { loadOptionalDependency } = loadOptionalDepsModuleWithMockedRequire(
      (name) => {
        if (name === "missing-export-package") {
          return { default: { OtherExport: 1 } };
        }
        throw missingModuleError(name);
      },
    );

    expect(() =>
      loadOptionalDependency(
        "missing-export-package",
        "custom provider",
        "ExpectedExport",
      ),
    ).toThrow(
      "Optional dependency 'missing-export-package' does not expose expected export 'ExpectedExport'",
    );
  });
});
