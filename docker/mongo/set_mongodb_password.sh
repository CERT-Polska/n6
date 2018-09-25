#!/bin/bash

echo "=> MongoDB CONFIG RUN!"

RET=1
while [[ RET -ne 0 ]]; do
    echo "=> Waiting for confirmation of MongoDB service startup"
    sleep 5
    mongo admin --eval "help" >/dev/null 2>&1
    RET=$?
done

echo "=> Creating user: $MONGODB_USER for $MONGODB_DATABASE database"
mongo $MONGODB_USER << EOF
use $MONGODB_DATABASE;
db.createUser({
  user: "$MONGODB_USER",
  pwd: "$MONGODB_PASS",
  roles: [
  {
    "role": "root",
    "db": "$MONGODB_DATABASE"
    },
  ]
});
EOF

sleep 1
echo "=> Creating user: $MONGODB_USER for $MONGODB_DATABASEN6 database"
mongo $MONGODB_DATABASE -u $MONGODB_USER -p $MONGODB_PASS << EOF
use $MONGODB_DATABASEN6;
db.createUser({
  user: "$MONGODB_USER",
  pwd: "$MONGODB_PASS",
  "roles": [
    {
      "role": "dbOwner",
      "db": "$MONGODB_DATABASEN6"
    },
  ]
});
EOF

echo "=> Done!"
touch /data/db/.mongodb_password_set

echo "========================================================================"
echo "You can now connect to this MongoDB server using:"
echo "    mongo $MONGODB_DATABASE -u $MONGODB_USER -p $MONGODB_PASS --host mongo --port 27017"
echo "    mongo $MONGODB_DATABASEN6 -u $MONGODB_USER -p $MONGODB_PASS --host mongo --port 27017"
echo "========================================================================"

