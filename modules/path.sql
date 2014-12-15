
CREATE VIEW `path_with_parent` AS
WITH RECURSIVE parent(folder, child, uri) AS (
    SELECT uri as folder, NULL, uri
    FROM node
UNION ALL
    SELECT
        rtrim(rtrim(folder,
            '%-._0123456789' ||
            'ABCDEFGHIJKLMNOPQRSTUVWXYZ' ||
            'abcdefghijklmnopqrstuvwxyz'
        ), '/') as folder,
        folder as child,
        uri
    FROM parent
    WHERE
        rtrim(rtrim(folder,
            '%-._0123456789' ||
            'ABCDEFGHIJKLMNOPQRSTUVWXYZ' ||
            'abcdefghijklmnopqrstuvwxyz'
        ), '/') LIKE "path://%/_%"
) SELECT * FROM parent WHERE child IS NOT NULL;

CREATE TRIGGER `path_parent` AFTER INSERT ON `node`
WHEN new.uri LIKE "path://%/_%"
BEGIN
    INSERT OR IGNORE INTO node
    SELECT folder, 'folder' FROM path_with_parent WHERE uri=new.uri;
    INSERT OR IGNORE INTO edge
    SELECT folder, child FROM path_with_parent WHERE uri=new.uri;
END;

