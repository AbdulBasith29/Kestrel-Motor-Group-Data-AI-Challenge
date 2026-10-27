select table_name,column_name from information_schema.columns
where table_schema='gold_staging' and lower(column_name) in
 ('comment','comments','proposed_comment','customer','customer_name','staff','staff_name','phone','email','rego','source_ref','customer_number','name_spans','name_mentions')
