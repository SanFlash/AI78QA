from typing import Any

def normalize_element(observation: dict[str, Any]) -> dict[str, Any]:
    features = observation.get('features') or {}
    name = str(observation.get('semantic_name') or features.get('name') or '')[:240]
    return {
        'tag': str(features.get('tag') or '').lower(),
        'role': str(features.get('role') or '').lower(),
        'type': str(features.get('type') or '').lower(),
        'name_tokens': ' '.join(name.lower().split()),
        'has_test_id': bool(features.get('test_id')),
        'has_stable_id': bool(features.get('unique_hint')),
        'visible': bool(features.get('visible', False)),
        'enabled': bool(features.get('enabled', False)),
        'has_href': bool(features.get('href')),
    }
