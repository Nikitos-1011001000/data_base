import requests
from config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
from db import DBManager
from geo_utils import get_country_coordinates

OPEN_SKY_URL = "https://opensky-network.org/api/states/all"
HEADERS = {"User-Agent": "flight-project/1.0"}


def main():
    print("🚀 Запуск проекта: Авиаданные и PostgreSQL...")

    # 1. Подключение к БД
    try:
        db = DBManager(DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT)
        print("✅ Подключение к PostgreSQL успешно")
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return

    # 2. Создание таблиц
    db.create_tables()
    print("✅ Таблицы проверены/созданы")

    
    countries_list = ["Germany", "Poland", "Czech Republic", "Austria"]

    areas = {
        "Germany": [5.8663, 47.2701, 15.0419, 55.0562],
        "Poland": [14.1155, 49.0027, 24.1458, 54.8358],
        "Czech Republic": [12.0839, 48.5561, 18.8857, 51.0545],
        "Austria": [9.5476, 46.3735, 17.1610, 49.0196]
    }

    print(f"\n🌍 Используем тестовые зоны для {len(countries_list)} стран.")

    country_map = {}
    # 4. Сохраняем страны в БД
    print("Сохранение стран в базу данных...")

    countries_to_insert = []
    for country_name, coords in areas.items():
        min_lon, min_lat, max_lon, max_lat = coords

        # Считаем центр прямоугольника как примерные координаты
        avg_lon = (min_lon + max_lon) / 2
        avg_lat = (min_lat + max_lat) / 2

        countries_to_insert.append({
            "name": country_name,
            "min_lat": min_lat,      # <-- Должно быть min_lat
            "max_lat": max_lat,      # <-- Должно быть max_lat
            "min_lon": min_lon,      # <-- Должно быть min_lon
            "max_lon": max_lon       # <-- Должно быть max_lon
        })

    country_ids_map = db.insert_countries(countries_to_insert)

    if country_ids_map:
        print("✅ Страны успешно сохранены!")
        for name, cid in country_ids_map.items():
            country_map[name] = cid
            print(f"   -> {name}: ID {cid}")
    else:
        print("❌ Не удалось сохранить страны.")

    print("\n🎉 Этап сохранения стран завершён!")

    # 5. Сбор данных о самолетах и привязка к странам
    all_planes_to_insert = []
    print("\n✈ Сбор данных о самолетах с OpenSky Network...")

    for country_name, coords in areas.items():
        min_lon, min_lat, max_lon, max_lat = coords

        if country_name not in country_map:
            print(f"⚠️ Пропускаем {country_name}: нет ID в базе (возможно, не сохранена)")
            continue

        country_id = country_map[country_name]

        params = {
            "lamin": min_lat,
            "lamax": max_lat,
            "lomin": min_lon,
            "lomax": max_lon
        }

        try:
            resp = requests.get(OPEN_SKY_URL, params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            states = data.get("states", [])

            count_added = 0
            count_skipped = 0

            for i, st in enumerate(states):
                length = len(st)
                # st индексы: 0:icao, 1:callsign, ..., 16:lat, 17:lon
                lat, lon = None, None

                if length >= 18:
                    # Старый формат
                    lat, lon = st[16], st[17]
                elif length == 17:
                    # НОВЫЙ ФОРМАТ: пробуем взять индексы 5 и 6 (Lon, Lat)
                    # В API порядок: [..., longitude, latitude, ...]
                    lon = st[5]
                    lat = st[6]
                else:
                    count_skipped += 1
                    continue

                if lat is None or lon is None:
                    count_skipped += 1
                    continue

                if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                    # print(f"   [WARN] Плохие координаты у самолёта {i}: lat={lat}, lon={lon}")
                    count_skipped += 1
                    continue

                icao = st[0]
                if not icao:
                    count_skipped += 1
                    continue

                    # min_lat <= lat <= max_lat И min_lon <= lon <= max_lon
                if (min_lat <= lat <= max_lat and
                        min_lon <= lon <= max_lon):

                    icao24 = st[0]
                    callsign = st[1]
                    origin_country = st[2]
                    time_position = st[3]
                    last_contact = st[4]
                    longitude = lon  # Мы уже вычислили это ранее (индекс 5 API)
                    latitude = lat  # Мы уже вычислили это ранее (индекс 6 API)
                    baro_altitude = st[7]
                    on_ground = st[8]
                    velocity = st[9]
                    true_track = st[10]
                    vertical_rate = st[11]
                    squawk = st[12]  # Строка
                    spi = bool(st[13]) if st[13] is not None else False
                    country_id = country_id
                    # Формируем строку для БД.
                    # ВНИМАНИЕ: Количество элементов должно совпадать с колонками в таблице!

                    row = (
                        icao24,
                        callsign,
                        origin_country,
                        time_position,
                        last_contact,
                        longitude,
                        latitude,
                        baro_altitude,
                        on_ground,
                        velocity,
                        true_track,
                        vertical_rate,
                        squawk,
                        spi,
                        country_id
                    )
                    all_planes_to_insert.append(row)
                    count_added += 1
                else:
                    pass

            print(f"   ✅ Зона '{country_name}': всего записей {len(states)}, пропущено неполных {count_skipped}, сохранено {count_added}")

        except Exception as e:
            print(f"⚠️ Ошибка при запросе для зоны '{country_name}': {e}")

        import time
        time.sleep(5)

    # 6. Массовая вставка в БД
    if all_planes_to_insert:
        print(f"\nЗагрузка {len(all_planes_to_insert)} записей о самолетах в PostgreSQL...")
        db.insert_aeroplanes(all_planes_to_insert, country_map)
        print("✅ Данные о самолетах загружены!")
    else:
        print("\n⚠️ Самолеты не найдены в указанных зонах.")

    # 7. ДЕМОСТРАЦИЯ РАБОТЫ (Отчеты для наставника)
    print("\n" + "=" * 50)
    print("���ЧЕТ ПО КРИТЕРИЯМ ОЦЕНКИ")
    print("=" * 50)

    print("\n1. Количество самолетов по странам:")
    for row in db.get_countries_and_aeroplanes_count():
        print(f"   {row[0]}: {row[1]} шт.")

    avg_spd = db.get_avg_speed()
    print(f"\n2. Средняя скорость всех самолетов: {avg_spd:.2f} м/с")

    fast_planes = db.get_aeroplanes_with_higher_speed()
    print(f"3. Самолетов быстрее средней скорости: {len(fast_planes)} шт.")
    if fast_planes:
        print(f"   Пример быстрого борта: {fast_planes[0]['callsign']} ({fast_planes[0]['velocity']:.1f} м/с)")

    aca_planes = db.get_aeroplanes_with_keyword("ACA")
    print(f"4. Самолетов с 'ACA' в позывном: {len(aca_planes)} шт.")

    print("\n🎉 Проект выполнен успешно!")
    db.close()


if __name__ == "__main__":
    main()
