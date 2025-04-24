

def init_reset(env):
    env.cr.execute("""
                update ir_config_parameter set value = ('' || CURRENT_TIMESTAMP(0)::timestamp without time zone), create_date = now() where key = 'database.create_date';
                update ir_config_parameter set value = ('' || (CURRENT_TIMESTAMP(0)+ interval '2 month')::timestamp without time zone), create_date = now() where key = 'database.expiration_date';
                update ir_config_parameter set value = (SUBSTRING(value,1, (LENGTH(value)-2))||(random() * 10 + 1)::int) where key = 'database.uuid';
               """)