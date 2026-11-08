-- Демо-база бандла sqlite: пакеты репозитория kt (/var/lib/kt/index) и их зависимости.
-- Собрана в самой машине: sqlite3 ~/packages.db < ~/packages.sql (рядом - список поставленных,
-- ls /var/lib/kt/pkg > /tmp/installed).
.mode tabs
CREATE TEMP TABLE raw(name TEXT, size TEXT, deps TEXT, description TEXT);
.import /var/lib/kt/index raw
CREATE TEMP TABLE inst(name TEXT);
.import /tmp/installed inst

CREATE TABLE packages(
  name TEXT PRIMARY KEY,
  download_kb INTEGER,   -- скачать, КБ
  installed_kb INTEGER,  -- в машине, КБ
  installed INTEGER,     -- 1 - стоит в этой машине
  description TEXT
);
INSERT INTO packages
SELECT name,
       CAST(substr(size, 1, instr(size, '/') - 1) AS INTEGER),
       CAST(substr(size, instr(size, '/') + 1) AS INTEGER),
       name IN (SELECT name FROM inst),
       description
FROM raw;

-- зависимость вида a|b - любой из пакетов, одной строкой
CREATE TABLE dependencies(package TEXT REFERENCES packages(name), dependency TEXT);
WITH RECURSIVE split(package, dep, rest) AS (
  SELECT name, '', deps || ' ' FROM raw
  UNION ALL
  SELECT package, substr(rest, 1, instr(rest, ' ') - 1), substr(rest, instr(rest, ' ') + 1)
  FROM split WHERE rest <> ''
)
INSERT INTO dependencies SELECT package, dep FROM split WHERE dep <> '';
CREATE INDEX dependencies_package ON dependencies(package);

CREATE VIEW biggest AS
SELECT name, installed_kb, description FROM packages ORDER BY installed_kb DESC LIMIT 20;

-- Попробовать во вкладке Execute SQL:
--
-- от кого зависит больше всего пакетов
--   SELECT dependency, count(*) AS n FROM dependencies GROUP BY dependency ORDER BY n DESC LIMIT 10;
--
-- всё, что потянет python-matplotlib, и сколько это в машине
--   WITH RECURSIVE need(name) AS (
--     SELECT 'python-matplotlib'
--     UNION SELECT d.dependency FROM dependencies d JOIN need ON d.package = need.name
--   )
--   SELECT count(*), sum(installed_kb) / 1024 AS mb FROM packages WHERE name IN need;
