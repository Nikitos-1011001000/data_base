import psycopg2
from psycopg2 import sql, extras

class DBManager:
    def __init__(self, dbname, user, password, host="localhost", port=5432):
        self.conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        self.cur = self.conn.cursor()

    def create_tables(self):
        """Создает таблицы countries и aeroplanes, если их ещё нет."""
        with self.conn.cursor() as cur:
            # Таблица для стран (храним зоны поиска)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS countries (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    min_lon DOUBLE PRECISION,
                    min_lat DOUBLE PRECISION,
                    max_lon DOUBLE PRECISION,
                    max_lat DOUBLE PRECISION
                );
            """)

            cur.execute("""
                    CREATE TABLE IF NOT EXISTS aeroplanes (
                    icao24 VARCHAR(8) PRIMARY KEY,
                    callsign VARCHAR(20),
                    origin_country VARCHAR(100),
                    time_position TIMESTAMP,
                    last_contact TIMESTAMP,
                    longitude DOUBLE PRECISION,
                    latitude DOUBLE PRECISION,
                    baro_altitude DOUBLE PRECISION,
                    on_ground BOOLEAN,
                    velocity DOUBLE PRECISION,
                    true_track DOUBLE PRECISION,
                    vertical_rate DOUBLE PRECISION,
                    squawk VARCHAR(4),
                    spi BOOLEAN,
                    country_id INTEGER
                    );
                """)

        self.conn.commit()
    print("✅ Таблицы созданы или уже существуют.")

    def close(self):
        self.cur.close()
        self.conn.close()

    def insert_countries(self, countries):
        """countries: список dict с ключами name, latitude, longitude"""
        insert_query = """
                    INSERT INTO countries (name, min_lat, max_lat, min_lon, max_lon)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        min_lat = EXCLUDED.min_lat,
                        max_lat = EXCLUDED.max_lat,
                        min_lon = EXCLUDED.min_lon,
                        max_lon = EXCLUDED.max_lon
                    RETURNING id;
                """
        country_ids = {}

        with self.conn.cursor() as cur:
            for c in countries:
                # СТРОГО 5 значений в том же порядке, что и в INSERT выше
                data = (
                    c["name"],
                    c["min_lat"],
                    c["max_lat"],
                    c["min_lon"],
                    c["max_lon"]
                )
                cur.execute(insert_query, data)
                row = cur.fetchone()

                if row:
                    country_ids[c["name"]] = row[0]
                else:
                    # Если страна уже есть, получаем ID
                    cur.execute("SELECT id FROM countries WHERE name = %s", (c["name"],))
                    res = cur.fetchone()
                    if res:
                        country_ids[c["name"]] = res[0]

            self.conn.commit()
            return country_ids

    def insert_aeroplanes(self, planes_data, country_map):
        if not planes_data:
            print("⚠️ Нет данных для вставки.")
            return

        query = """
            INSERT INTO aeroplanes (
                icao24, callsign, origin_country, time_position, last_contact,
                longitude, latitude, baro_altitude, on_ground, velocity,
                true_track, vertical_rate, squawk, spi, country_id
            ) VALUES %s
            ON CONFLICT (icao24) DO UPDATE SET
                callsign = EXCLUDED.callsign,
                origin_country = EXCLUDED.origin_country,
                time_position = EXCLUDED.time_position,
                last_contact = EXCLUDED.last_contact,
                longitude = EXCLUDED.longitude,
                latitude = EXCLUDED.latitude,
                baro_altitude = EXCLUDED.baro_altitude,
                on_ground = EXCLUDED.on_ground,
                velocity = EXCLUDED.velocity,
                true_track = EXCLUDED.true_track,
                vertical_rate = EXCLUDED.vertical_rate,
                squawk = EXCLUDED.squawk,
                spi = EXCLUDED.spi,
                country_id = EXCLUDED.country_id;
        """

        with self.conn.cursor() as cur:
            from psycopg2.extras import execute_values
            execute_values(cur, query, planes_data)

        self.conn.commit()
    def get_countries_and_aeroplanes_count(self):
        query = """
            SELECT c.name, COUNT(a.icao24) AS planes_count
            FROM countries c
            LEFT JOIN aeroplanes a ON c.id = a.country_id
            GROUP BY c.id, c.name
            ORDER BY planes_count DESC;
        """
        self.cur.execute(query)
        return self.cur.fetchall()

    def get_all_aeroplanes(self):
        query = "SELECT * FROM aeroplanes;"
        self.cur.execute(query)
        cols = [desc[0] for desc in self.cur.description]
        return [dict(zip(cols, row)) for row in self.cur.fetchall()]

    def get_avg_speed(self):
        query = "SELECT AVG(velocity) FROM aeroplanes WHERE velocity IS NOT NULL;"
        self.cur.execute(query)
        row = self.cur.fetchone()
        return row[0] if row and row[0] is not None else 0.0

    def get_aeroplanes_with_higher_speed(self):
        avg_speed = self.get_avg_speed()
        query = """
            SELECT * FROM aeroplanes
            WHERE velocity > %s AND velocity IS NOT NULL;
        """
        self.cur.execute(query, (avg_speed,))
        cols = [desc[0] for desc in self.cur.description]
        return [dict(zip(cols, row)) for row in self.cur.fetchall()]

    def get_aeroplanes_with_keyword(self, keyword):
        query = """
            SELECT * FROM aeroplanes
            WHERE callsign ILIKE %s;
        """
        pattern = f"%{keyword}%"
        self.cur.execute(query, (pattern,))
        cols = [desc[0] for desc in self.cur.description]
        return [dict(zip(cols, row)) for row in self.cur.fetchall()]