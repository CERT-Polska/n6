db.createUser({
  user: "admin",
  pwd: "password",
  "roles": [{
          "role": "dbOwner",
          "db": "n6"
      },
      {
          "role": "root",
          "db": "admin"
      }
  ]
});

db.createRole({
  role: "readWriteSystem",
  privileges: [
    {
      resource: {
          db: "n6",
          collection: "system.indexes"
      },
      actions: ["changeStream", "collStats", "convertToCapped", "createCollection", "createIndex", "dbHash", "dbStats", "dropCollection", "dropIndex", "emptycapped", "find", "insert", "killCursors", "listCollections", "listIndexes", "planCacheRead", "remove", "renameCollectionSameDB", "update"]
    }
  ],
  roles: []
});

db.grantRolesToUser('admin', ['readWriteSystem']);
