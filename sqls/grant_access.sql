grant {role_name} to {username} WITH INHERIT TRUE;

insert into roles_mapping(username, role) values ('{username}', '{role_name}')