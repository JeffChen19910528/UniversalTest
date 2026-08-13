// Intentional runtime error on load, for browser-test fixture purposes:
// proves console/page-error evidence capture without treating it as an
// assertion failure unless a test explicitly asserts on error counts.
undefinedFunctionCausesRuntimeError();
