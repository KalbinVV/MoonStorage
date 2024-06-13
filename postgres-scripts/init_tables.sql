create table if not exists roles (
	name varchar primary key
);

create table if not exists registry (
	cid varchar primary key,
	filename varchar not null,
	private_key varchar(256) not null,
	owned_by varchar not null,
	role varchar not null,
	foreign key(role) references roles(name) on delete restrict
);

CREATE TABLE if not exists user_roles (
	id bigserial primary key,
	username varchar NOT NULL,
	role varchar NOT NULL,
	valid_until date NULL,
	foreign key(role) references roles(name) on delete restrict
);

CREATE OR REPLACE VIEW public.registry_view
AS SELECT cid,
    filename,
    private_key,
    owned_by,
    role
   FROM registry rg
  WHERE (role::text IN ( SELECT ur.role
           FROM user_roles ur
          WHERE ur.username::text = CURRENT_USER));

create function check_role() returns trigger as $check_role$
	begin
		if new.role not in ( SELECT ur.role
           FROM user_roles ur
          WHERE ur.username::text = CURRENT_USER) then
         raise exception '% не может быть добавлено, недостаточно превилегий', new.cid;
        end if;

        new.owned_by = current_user;

       return new;
	end;
$check_role$ language plpgsql;

create trigger check_role_before_insert
before insert on registry
for each row execute procedure check_role();