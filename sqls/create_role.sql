create role {role_name} noinherit;

revoke all privileges on database ipfs from {role_name};

grant select, delete, update on table registry to {role_name};

grant insert, update on table registry_data to {role_name};

grant select on table user_roles to {role_name};

grant select, delete, update on table directories to {role_name};

grant insert on table directories_data to {role_name};

grant usage, select on sequence registry_data_id_seq to {role_name};
grant usage, select on sequence directories_data_id_seq to {role_name};

insert into roles(name) values('{role_name}');