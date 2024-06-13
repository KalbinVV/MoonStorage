create role {role_name} noinherit;

revoke all privileges on database ipfs from {role_name};

grant select on table registry to {role_name};
grant insert on table registry_data to {role_name};
grant select on table user_roles to {role_name};

insert into roles(name) values('{role_name}');