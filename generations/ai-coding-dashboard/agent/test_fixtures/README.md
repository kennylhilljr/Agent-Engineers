# A2UI Test Fixtures

This directory contains JSON test fixtures for validating A2UI protocol compliance.

## Valid Messages

- `valid_message_1.json` - Basic card with text and button
- `valid_message_2.json` - Container with grid and badges
- `valid_message_3.json` - Data model update with input

## Invalid Messages (Missing Fields)

- `invalid_missing_type.json` - Component missing required `type` field
- `invalid_missing_id.json` - Component missing required `id` field
- `invalid_missing_props.json` - Component missing required `props` field
- `invalid_bad_message_type.json` - Invalid messageType value

## Security Violations

- `security_unauthorized_component.json` - Component type not in catalog
- `security_script_injection.json` - Script injection attempt via component type

## Edge Cases

- `edge_circular_reference.json` - Circular reference between components
- `edge_duplicate_ids.json` - Duplicate component IDs
- `edge_missing_child_ref.json` - Reference to non-existent child

## Usage

```python
from a2ui_validator import validate_a2ui_file

# Validate a fixture
result = validate_a2ui_file('agent/test_fixtures/valid_message_1.json')
print(result)
```

```typescript
import { validateA2UIMessage } from '@/lib/a2ui-validator';
import validMessage from './test_fixtures/valid_message_1.json';

const result = validateA2UIMessage(validMessage);
console.log(result);
```
