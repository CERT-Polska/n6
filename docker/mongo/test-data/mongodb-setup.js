db.createUser({
  user: "admin",
  pwd: "password",
  "roles": [{"role": "dbOwner", "db": "n6"},
            {"role": "root", "db": "admin"},
  ]
});