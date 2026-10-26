WITH RECURSIVE reachable(item,revision) AS (
 SELECT parent_item,parent_revision FROM edges WHERE component_item=? AND component_revision=?
 UNION
 SELECT e.parent_item,e.parent_revision FROM edges e JOIN reachable r
 ON e.component_item=r.item AND e.component_revision=r.revision
)
SELECT item,revision FROM reachable WHERE NOT (item=? AND revision=?);
