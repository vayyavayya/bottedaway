-- Storage: a single private bucket for bill photos, generated PDFs, and statements.
-- Files are laid out as  <household_id>/<document_id>/<filename>  so access can be
-- checked from the first path segment.

insert into storage.buckets (id, name, public)
values ('documents', 'documents', false)
on conflict (id) do nothing;

-- Only members of the household in the first path segment may touch the file.
create policy "documents read"  on storage.objects
  for select using (
    bucket_id = 'documents'
    and is_household_member(((storage.foldername(name))[1])::uuid)
  );

create policy "documents insert" on storage.objects
  for insert with check (
    bucket_id = 'documents'
    and is_household_member(((storage.foldername(name))[1])::uuid)
  );

create policy "documents update" on storage.objects
  for update using (
    bucket_id = 'documents'
    and is_household_member(((storage.foldername(name))[1])::uuid)
  );

create policy "documents delete" on storage.objects
  for delete using (
    bucket_id = 'documents'
    and is_household_member(((storage.foldername(name))[1])::uuid)
  );
