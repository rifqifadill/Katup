import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo


def import_traffic(source, output, source_name, license_name, timezone='Asia/Jakarta'):
    groups = {}
    seen = set()
    with Path(source).open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not {'timestamp', 'road_id', 'direction', 'vehicle_count', 'speed_kmh'} <= set(reader.fieldnames or []):
            raise ValueError('Kolom CSV belum lengkap')
        for line, row in enumerate(reader, 2):
            stamp = datetime.fromisoformat(row['timestamp'])
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=ZoneInfo(timezone))
            stamp = stamp.astimezone(ZoneInfo(timezone))
            count, speed = float(row['vehicle_count']), float(row['speed_kmh'])
            if not 0 <= count <= 100000 or not count.is_integer() or not 0 <= speed <= 200:
                raise ValueError(f'Nilai di baris {line} di luar batas')
            road, direction = row['road_id'].strip(), row['direction'].strip()
            if not road or not direction:
                raise ValueError(f'Ruas atau arah kosong di baris {line}')
            identity = (stamp.isoformat(), road, direction)
            if identity in seen:
                raise ValueError(f'Data ganda di baris {line}')
            seen.add(identity)
            bucket = stamp.replace(minute=stamp.minute // 15 * 15, second=0, microsecond=0)
            groups.setdefault((bucket.isoformat(), road, direction), []).append((count, speed))
    if not groups:
        raise ValueError('CSV tidak berisi pengamatan')
    rows = [{'timestamp': key[0], 'road_id': key[1], 'direction': key[2], 'vehicle_count': int(sum(x[0] for x in values)), 'speed_kmh': round(mean(x[1] for x in values), 3), 'samples': len(values)} for key, values in sorted(groups.items())]
    dates = sorted({row['timestamp'][:10] for row in rows})
    holdout = dates[max(1, int(len(dates) * .8)):] if len(dates) > 1 else []
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    for name, selected in [('observations.csv', rows), ('calibration.csv', [r for r in rows if r['timestamp'][:10] not in holdout]), ('holdout.csv', [r for r in rows if r['timestamp'][:10] in holdout])]:
        with (destination / name).open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(selected)
    report = {'source': source_name, 'license': license_name, 'timezone': timezone, 'input_rows': len(seen), 'bins': len(rows), 'dates': dates, 'holdout_dates': holdout, 'resolution_minutes': 15, 'speed_aggregation': 'mean of supplied speed samples, not vehicle-weighted', 'volume_semantics': 'counts must cover non-overlapping observation intervals', 'status': 'Prepared observations, not LLM training and not automatically applied to SUMO demand'}
    (destination / 'provenance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Menyiapkan data pengamatan per ruas dan arah')
    parser.add_argument('csv')
    parser.add_argument('--output', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--license', required=True)
    args = parser.parse_args()
    print(json.dumps(import_traffic(args.csv, args.output, args.source, args.license), indent=2))
