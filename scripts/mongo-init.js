// MongoDB Initialization Script for GlobeCo Order Generation Service
// Sets up database with proper collections, indexes, and configurations

// Initialize replica set if not already done
try {
    print('Checking replica set status...');
    rs.status();
    print('Replica set already initialized.');
} catch (err) {
    print('Initializing replica set...');
    rs.initiate({
        _id: 'rs0',
        members: [
            { _id: 0, host: 'globeco-order-generation-service-mongodb:27017' }
        ]
    });

    // Wait for primary election
    print('Waiting for primary election...');
    while (!rs.isMaster().ismaster) {
        sleep(100);
    }
    print('Primary elected successfully.');
}

// Switch to the application database
db = db.getSiblingDB('globeco_dev');

print('Initializing GlobeCo Order Generation Service database...');

// ===================================================================
// Create Collections with Validation
// ===================================================================

// Investment Models Collection
print('Creating models collection...');
db.createCollection('models', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['name', 'positions', 'portfolios', 'version', 'created_at', 'updated_at'],
            properties: {
                name: {
                    bsonType: 'string',
                    description: 'Model name must be a string and is required'
                },
                positions: {
                    bsonType: 'array',
                    description: 'Positions must be an array',
                    items: {
                        bsonType: 'object',
                        required: ['security_id', 'target', 'low_drift', 'high_drift'],
                        properties: {
                            security_id: {
                                bsonType: 'string',
                                pattern: '^[A-Za-z0-9]{24}$',
                                description: 'Security ID must be exactly 24 alphanumeric characters'
                            },
                            target: {
                                bsonType: 'decimal',
                                minimum: 0,
                                maximum: 0.95,
                                description: 'Target percentage must be between 0 and 0.95'
                            },
                            low_drift: {
                                bsonType: 'decimal',
                                minimum: 0,
                                maximum: 1,
                                description: 'Low drift must be between 0 and 1'
                            },
                            high_drift: {
                                bsonType: 'decimal',
                                minimum: 0,
                                maximum: 1,
                                description: 'High drift must be between 0 and 1'
                            }
                        }
                    }
                },
                portfolios: {
                    bsonType: 'array',
                    description: 'Portfolios must be an array of strings',
                    items: {
                        bsonType: 'string'
                    }
                },
                version: {
                    bsonType: 'int',
                    minimum: 1,
                    description: 'Version must be a positive integer'
                },
                last_rebalance_date: {
                    bsonType: ['date', 'null'],
                    description: 'Last rebalance date must be a date or null'
                },
                created_at: {
                    bsonType: 'date',
                    description: 'Created date is required'
                },
                updated_at: {
                    bsonType: 'date',
                    description: 'Updated date is required'
                }
            }
        }
    }
});

// ===================================================================
// Create Indexes for Performance
// ===================================================================

print('Creating indexes...');

// Models collection indexes
db.models.createIndex({ 'name': 1 }, { unique: true, name: 'idx_models_name_unique' });
db.models.createIndex({ 'portfolios': 1 }, { name: 'idx_models_portfolios' });
db.models.createIndex({ 'last_rebalance_date': 1 }, { name: 'idx_models_last_rebalance' });
db.models.createIndex({ 'positions.security_id': 1 }, { name: 'idx_models_security_id' });
db.models.createIndex({ 'version': 1 }, { name: 'idx_models_version' });
db.models.createIndex({ 'created_at': -1 }, { name: 'idx_models_created_desc' });
db.models.createIndex({ 'updated_at': -1 }, { name: 'idx_models_updated_desc' });

// Compound indexes for common queries
db.models.createIndex(
    { 'portfolios': 1, 'last_rebalance_date': -1 },
    { name: 'idx_models_portfolio_rebalance' }
);

db.models.createIndex(
    { 'name': 1, 'version': 1 },
    { name: 'idx_models_name_version' }
);

// ===================================================================
// Insert Sample Data for Development
// ===================================================================

print('Inserting sample development data...');

// Sample investment models
const sampleModels = [
    {
        name: 'Balanced Growth Portfolio',
        positions: [
            {
                security_id: 'TECH123456789012345678AB',
                target: NumberDecimal('0.40'),
                low_drift: NumberDecimal('0.02'),
                high_drift: NumberDecimal('0.05')
            },
            {
                security_id: 'BOND123456789012345678AB',
                target: NumberDecimal('0.30'),
                low_drift: NumberDecimal('0.01'),
                high_drift: NumberDecimal('0.03')
            },
            {
                security_id: 'REIT123456789012345678AB',
                target: NumberDecimal('0.20'),
                low_drift: NumberDecimal('0.03'),
                high_drift: NumberDecimal('0.07')
            }
        ],
        portfolios: ['portfolio123456789012345'],
        version: 1,
        last_rebalance_date: null,
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        name: 'Conservative Income Portfolio',
        positions: [
            {
                security_id: 'BOND123456789012345678AB',
                target: NumberDecimal('0.60'),
                low_drift: NumberDecimal('0.01'),
                high_drift: NumberDecimal('0.02')
            },
            {
                security_id: 'CASH123456789012345678AB',
                target: NumberDecimal('0.25'),
                low_drift: NumberDecimal('0.005'),
                high_drift: NumberDecimal('0.01')
            },
            {
                security_id: 'REIT123456789012345678AB',
                target: NumberDecimal('0.10'),
                low_drift: NumberDecimal('0.02'),
                high_drift: NumberDecimal('0.04')
            }
        ],
        portfolios: ['portfolio123456789012346', 'portfolio123456789012347'],
        version: 1,
        last_rebalance_date: null,
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        name: 'Aggressive Growth Portfolio',
        positions: [
            {
                security_id: 'TECH123456789012345678AB',
                target: NumberDecimal('0.70'),
                low_drift: NumberDecimal('0.03'),
                high_drift: NumberDecimal('0.08')
            },
            {
                security_id: 'EMRG123456789012345678AB',
                target: NumberDecimal('0.15'),
                low_drift: NumberDecimal('0.05'),
                high_drift: NumberDecimal('0.10')
            },
            {
                security_id: 'INTL123456789012345678AB',
                target: NumberDecimal('0.10'),
                low_drift: NumberDecimal('0.03'),
                high_drift: NumberDecimal('0.06')
            }
        ],
        portfolios: ['portfolio123456789012348'],
        version: 1,
        last_rebalance_date: null,
        created_at: new Date(),
        updated_at: new Date()
    }
];

// Insert sample models
db.models.insertMany(sampleModels);

// ===================================================================
// Create Database Users (Development only)
// ===================================================================

print('Creating database users...');

// Create application user with read/write permissions
db.createUser({
    user: 'globeco_app',
    pwd: 'dev_password_123',
    roles: [
        {
            role: 'readWrite',
            db: 'globeco_dev'
        }
    ]
});

// Create read-only user for reporting
db.createUser({
    user: 'globeco_readonly',
    pwd: 'readonly_password_123',
    roles: [
        {
            role: 'read',
            db: 'globeco_dev'
        }
    ]
});

// ===================================================================
// Database Configuration
// ===================================================================

print('Configuring database settings...');

// Set collection read preference
db.runCommand({
    collMod: 'models',
    validationLevel: 'strict',
    validationAction: 'error'
});

// ===================================================================
// Verification
// ===================================================================

print('Verifying database setup...');

// Check collections
const collections = db.getCollectionNames();
print('Collections created: ' + collections.join(', '));

// Check indexes
const indexes = db.models.getIndexes();
print('Indexes created on models collection: ' + indexes.length);

// Check sample data
const modelCount = db.models.countDocuments();
print('Sample models inserted: ' + modelCount);

// Check users
const users = db.getUsers();
print('Database users created: ' + users.length);

print('Database initialization completed successfully!');

// ===================================================================
// Health Check Function
// ===================================================================

// Create a simple health check function
db.system.js.save({
    _id: 'healthCheck',
    value: function() {
        var result = {
            timestamp: new Date(),
            status: 'healthy',
            collections: db.getCollectionNames().length,
            models_count: db.models.countDocuments(),
            indexes_count: db.models.getIndexes().length
        };

        return result;
    }
});

print('Health check function created. Use db.eval(healthCheck) to check database health.');
