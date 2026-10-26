#!/usr/bin/env bash
echo "🔄 Starting Docker containers..."
docker compose up -d
sleep 10

echo "🗄️ Checking database..."
USERS=$(docker compose exec -T db psql -U nrims -d nrims -tAc "SELECT count(*) FROM users;" 2>/dev/null | tr -d '[:space:]')

if [ "$USERS" = "0" ] || [ -z "$USERS" ]; then
    echo "⚠️ Database is empty. Seeding data..."
    docker compose exec worker python seed_master.py
    docker compose exec worker python seed_links.py
    docker compose exec worker python seed_inventory.py
    docker compose exec worker python seed_admin.py
    echo "✅ Database seeded!"
else
    echo "✅ Database already has $USERS users."
fi

echo "🚀 System is ready! Access frontend at http://localhost:8080"
