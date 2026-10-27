-- Controlled taxonomy; individual model prose never enters the reporting database.
select * from (values
 ('communication_follow_up','Communication and follow-up'),
 ('waiting_time_scheduling','Waiting time and scheduling'),
 ('workmanship_repair_quality','Workmanship and repair quality'),
 ('staff_service','Staff service'),('pricing_value','Pricing and value'),
 ('sales_process','Sales process'),('parts_availability','Parts availability'),
 ('vehicle_product','Vehicle or product'),('other','Other')) as t(theme_id, theme_name)
