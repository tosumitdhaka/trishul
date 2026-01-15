# Quick test
from services.config_service import Config
from services.db_service import DatabaseManager
from backend.services.oid_resolver_service import OIDResolverService


config = Config()
db_manager = DatabaseManager(config)
resolver = OIDResolverService(db_manager)

# Test batch resolve with instance OIDs
test_oids = [
    '1.3.6.1.2.1.2.2.1.2.1',
    '1.3.6.1.2.1.2.2.1.2.2',
    '1.3.6.1.2.1.2.2.1.3.1',
    '1.3.6.1.2.1.2.2.1.7.1',
    '1.3.6.1.2.1.2.2.1.8.1'
]

results = resolver.resolve_batch(test_oids)

print(f"Resolved {len(results)}/{len(test_oids)} OIDs:")
for oid, info in results.items():
    print(f"  {oid} -> {info['name']}")
