local stringify = pandoc.utils.stringify

local function is_metabool_true(v)
  return v == true or (type(v) == "table" and v.t == "MetaBool" and v.c == true)
end

local function unwrap_metalist(v)
  if type(v) == "table" and v.t == "MetaList" then
    return v.c or {}
  end
  return v
end

local function unwrap_metamap(v)
  if type(v) == "table" and v.t == "MetaMap" then
    return v.c or {}
  end
  return v
end

local function meta_to_string(v)
  if v == nil then
    return nil
  end
  return stringify(v)
end

local function is_author_map(v)
  v = unwrap_metamap(v)
  if type(v) ~= "table" then
    return false
  end
  return v.name ~= nil
    or v.affiliations ~= nil
    or v.affiliation ~= nil
    or v.email ~= nil
    or v.corresponding ~= nil
    or v.orcid ~= nil
end

local function join_nonempty(parts, sep)
  local out = {}
  for _, part in ipairs(parts) do
    if part ~= nil and part ~= "" then
      out[#out + 1] = part
    end
  end
  return table.concat(out, sep or ", ")
end

local function normalize_affiliation(aff)
  if aff == nil then
    return nil
  end
  if type(aff) == "string" then
    return aff
  end
  if type(aff) ~= "table" then
    return meta_to_string(aff)
  end

  -- MetaInlines / Inlines (or other pandoc list-like values) stringify cleanly.
  -- If this is a structured affiliation map, build a single string.
  if aff.name ~= nil or aff.department ~= nil or aff.address ~= nil or aff.city ~= nil or aff.country ~= nil then
    local name = meta_to_string(aff.name)
    local department = meta_to_string(aff.department)
    local address = meta_to_string(aff.address)
    local city = meta_to_string(aff.city)
    local region = meta_to_string(aff.region)
    local country = meta_to_string(aff.country)
    local postal = meta_to_string(aff["postal-code"]) or meta_to_string(aff.postal_code)
    return join_nonempty({ name, department, address, city, region, postal, country }, ", ")
  end

  return meta_to_string(aff)
end

local function author_display_name(a)
  if type(a) ~= "table" then
    return meta_to_string(a)
  end

  local name_val = a.name
  if type(name_val) == "table" then
    local name_map = unwrap_metamap(name_val)
    if type(name_map) == "table" then
      if name_map.literal ~= nil then
        return meta_to_string(name_map.literal)
      end
      local given = meta_to_string(name_map.given)
      local family = meta_to_string(name_map.family)
      if given and family then
        return given .. " " .. family
      end
    end
  end

  return meta_to_string(a.name) or meta_to_string(a.literal) or meta_to_string(a)
end

local function author_is_corresponding(a)
  if is_metabool_true(a.corresponding) or is_metabool_true(a["corresponding-author"]) then
    return true
  end
  if type(a.attributes) == "table" then
    local attrs = unwrap_metamap(a.attributes)
    local v = attrs.corresponding or attrs["corresponding-author"]
    local s = meta_to_string(v)
    if s and s:lower() == "true" then
      return true
    end
  end
  return false
end

local function guess_lead_author(author_name)
  if not author_name or author_name == "" then
    return nil
  end
  local parts = {}
  for part in author_name:gmatch("%S+") do
    parts[#parts + 1] = part
  end
  return parts[#parts]
end

function Meta(meta)
  local authors = meta.authors
  local authors_list = unwrap_metalist(authors)
  if authors == nil
    or type(authors_list) ~= "table"
    or authors_list[1] == nil
    or not is_author_map(authors_list[1]) then
    authors = meta.author
  end

  local author_list = {}
  if type(authors) == "table" then
    author_list = unwrap_metalist(authors) or authors
  elseif authors ~= nil then
    author_list = { authors }
  end

  local affiliation_name_by_id = {}
  local meta_affiliations = unwrap_metalist(meta.affiliations)
  if type(meta_affiliations) == "table" then
    for _, aff0 in ipairs(meta_affiliations) do
      local aff = unwrap_metamap(aff0)
      if type(aff) == "table" then
        local id = meta_to_string(aff.id)
        local name = meta_to_string(aff.name)
        if id and name then
          affiliation_name_by_id[id] = name
        end
      end
    end
  end

  local aff_index_by_text = {}
  local aff_list = {}

  local function intern_affiliation(text)
    if text == nil or text == "" then
      return nil
    end
    local existing = aff_index_by_text[text]
    if existing ~= nil then
      return existing
    end
    local idx = #aff_list + 1
    aff_index_by_text[text] = idx
    aff_list[#aff_list + 1] = { index = idx, text = text }
    return idx
  end

  local normalized_authors = {}
  local first_author_name = nil
  local correspondence_raw = meta.correspondence or meta.corresponding or meta["correspondence-email"]
  local correspondence_email = meta_to_string(correspondence_raw)

  for _, a in ipairs(author_list) do
    a = unwrap_metamap(a)
    local name
    local affiliations = {}
    local email = nil
    local corresponding = false

    if is_author_map(a) then
      name = author_display_name(a)
      email = meta_to_string(a.email)
      corresponding = author_is_corresponding(a)

      local aff = a.affiliations or a.affiliation
      if aff ~= nil then
        aff = unwrap_metalist(aff) or aff
        local aff_type = pandoc.utils.type(aff)
        if aff_type == "Inlines" or aff_type == "Blocks" or type(aff) == "string" then
          affiliations[#affiliations + 1] = normalize_affiliation(aff)
        elseif type(aff) == "table" then
          for _, it0 in ipairs(aff) do
            local it = unwrap_metamap(it0)
            if type(it) == "table" and it.ref ~= nil then
              local ref = unwrap_metamap(it.ref)
              local id = meta_to_string(ref)
              affiliations[#affiliations + 1] = (id and affiliation_name_by_id[id]) or id or normalize_affiliation(it0)
            else
              affiliations[#affiliations + 1] = normalize_affiliation(it0)
            end
          end
        else
          affiliations[#affiliations + 1] = normalize_affiliation(aff)
        end
      end
    else
      name = meta_to_string(a)
    end

    if name and not first_author_name then
      first_author_name = name
    end

    local aff_indices = {}
    for _, aff_text in ipairs(affiliations) do
      local idx = intern_affiliation(aff_text)
      if idx ~= nil then
        aff_indices[#aff_indices + 1] = tostring(idx)
      end
    end

    if corresponding and not correspondence_email and email then
      correspondence_email = email
    end

    normalized_authors[#normalized_authors + 1] = {
      name = pandoc.MetaString(name or ""),
      ["affil-marks"] = pandoc.MetaString(table.concat(aff_indices, ",")),
      corresponding = pandoc.MetaBool(corresponding),
      email = email and pandoc.MetaString(email) or nil,
    }
  end

  local aff_meta_list = {}
  for _, it in ipairs(aff_list) do
    aff_meta_list[#aff_meta_list + 1] = {
      index = pandoc.MetaString(tostring(it.index)),
      text = pandoc.MetaString(it.text),
    }
  end

  meta["biorxiv-authors"] = pandoc.MetaList(normalized_authors)
  meta["biorxiv-affiliations"] = pandoc.MetaList(aff_meta_list)

  if meta.shorttitle == nil and meta.title ~= nil then
    meta.shorttitle = meta.title
  end
  if meta.leadauthor == nil and first_author_name ~= nil then
    meta.leadauthor = pandoc.MetaString(guess_lead_author(first_author_name) or "")
  end

  if correspondence_email ~= nil then
    if meta["correspondence-email"] == nil then
      meta["correspondence-email"] = pandoc.MetaString(correspondence_email)
    end
  end

  return meta
end
