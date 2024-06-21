create table if not exists roles (
	name varchar primary key
);

create table if not exists directories_data (
    id serial8 primary key,
    name varchar not null,
    parent_directory integer,
    role varchar not null,
    foreign key(role) references roles(name) on delete restrict,
    foreign key(parent_directory) references directories_data(id) on delete cascade
);

create table if not exists registry_data (
    id serial8 primary key,
	cid varchar,
	name varchar not null,
	secret_key bytea not null,
	owned_by varchar not null,
	role varchar not null,
	file_size integer not null,
	file_hash varchar(256) not null,
	uploaded_at timestamp DEFAULT now(),
	directory integer,
	foreign key(role) references roles(name) on delete restrict,
	foreign key(directory) references directories_data(id) on delete cascade
);

CREATE TABLE if not exists roles_mapping (
	id bigserial primary key,
	username varchar NOT NULL,
	role varchar NOT NULL,
	valid_until date NULL,
	foreign key(role) references roles(name) on delete restrict
);

CREATE OR REPLACE VIEW user_roles
AS SELECT role
    FROM roles_mapping rm
    where rm.username = current_user;

CREATE OR REPLACE VIEW registry
AS SELECT cid,
    name,
    secret_key,
    owned_by,
    role,
    file_size,
    file_hash,
    uploaded_at,
    directory
   FROM registry_data rg
  WHERE (role::text IN (select role from user_roles));

create or replace view directories
as select name,
    id,
    parent_directory,
    role
   from directories_data dd
  where (role::text in (select role from user_roles));

create function check_role_for_file() returns trigger as $check_role$
	begin
		if new.role not in (select role from user_roles) then
         raise exception '% не может быть добавлено, недостаточно привилегий', new.cid;
        end if;

        new.owned_by = current_user;

       return new;
	end;
$check_role$ language plpgsql;

create function check_role_for_directory() returns trigger as $check_role$
	begin
		if new.role not in (select role from user_roles) then
         raise exception '% не может быть добавлено, недостаточно привилегий', new.name;
        end if;

       return new;
	end;
$check_role$ language plpgsql;

create trigger check_role_before_insert_for_files
before insert on registry_data
for each row execute procedure check_role_for_file();

create trigger check_role_before_insert_for_directories
before insert on directories_data
for each row execute procedure check_role_for_directory();
