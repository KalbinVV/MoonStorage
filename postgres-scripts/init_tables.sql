create table if not exists roles (
	name varchar primary key
);

create table if not exists registry_data (
	cid varchar primary key,
	filename varchar not null,
	private_key bytea not null,
	owned_by varchar not null,
	role varchar not null,
	foreign key(role) references roles(name) on delete restrict
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
    filename,
    private_key,
    owned_by,
    role
   FROM registry_data rg
  WHERE (role::text IN (select role from user_roles));

create function check_role() returns trigger as $check_role$
	begin
		if new.role not in (select role from user_roles) then
         raise exception '% не может быть добавлено, недостаточно привилегий', new.cid;
        end if;

        new.owned_by = current_user;

       return new;
	end;
$check_role$ language plpgsql;

create trigger check_role_before_insert
before insert on registry_data
for each row execute procedure check_role();