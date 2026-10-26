SELECT rule_id FROM checks WHERE
 (kind='equal' AND a<>b) OR
 (kind='quantity' AND NOT (a>0 AND a<=b)) OR
 (kind='inspection-status' AND a<>'Accepted') OR
 (kind='certificate-status' AND a<>'Active') OR
 (kind='interval' AND NOT (a<=b AND b<c));
