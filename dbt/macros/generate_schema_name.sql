{# Use the schema name as written (gold), not "main_gold" #}
{% macro generate_schema_name(custom_schema_name, node) -%}
  {{ custom_schema_name or target.schema }}
{%- endmacro %}
