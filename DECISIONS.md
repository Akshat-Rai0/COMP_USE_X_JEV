# Resolved Decisions

This document tracks decisions that have been made during the development of Reflex Arc, including the rationale and implementation details.

## D2: Cua Driver Integration Approach

**Status**: ✅ Resolved Sep 23, 2026

### Decision
Use Python SDK (`from cua_driver import CuaDriver`) for Cua Driver integration.

### Options Considered
1. **Python SDK** (`cua-driver` package)
2. **CLI** (`cua-driver call` commands)

### Rationale for SDK Choice
- **Typed async API** that fits our architecture better than parsing CLI output
- **Fine-grained control** for the Body abstraction layer
- **Better error handling** and state management through native exceptions
- **Direct integration** with our orchestrator loop without subprocess overhead
- **No daemon IPC overhead** - `CuaDriver.create()` runs in-process
- **Better testing** - easier to mock and test than CLI subprocess calls

### Implementation Details
- File: `src/body/driver.py`
- Wrapper class: `Body` interface wrapping `CuaDriver.create()`
- Methods: `read_frontmost_window()`, `act(element_id, action_type, text=None)`
- Includes `FakeBody` for testing with recorded fixtures

### References
- Cua SDK Documentation: https://cua.ai/docs/reference/cua-driver/sdk-reference
- SDK Installation: `pip install cua-driver`
- SDK Example: https://cua.ai/docs/how-to-guides/driver/use-sdk-in-process