-- osm2pgsql flex style: OSM ways and POI geometry into a dedicated schema.
--
-- This file deliberately stores OSM ways, not graph edges. No topology is
-- built here; routing remains an OTP responsibility.

local srid = 4326
local tables = {}

local function tag(tags, key)
    local value = tags[key]
    if value == nil then
        return nil
    end
    value = tostring(value)
    if value == "" then
        return nil
    end
    return value
end

local poi_keys = {
    "amenity", "shop", "tourism", "leisure", "office", "healthcare",
    "historic", "public_transport", "railway", "place", "aeroway",
    "craft", "emergency", "military", "man_made",
}

local function poi_category(tags)
    for _, key in ipairs(poi_keys) do
        local value = tag(tags, key)
        if value then
            return key, value
        end
    end
    if tag(tags, "building") and (tag(tags, "name") or tag(tags, "name:it") or tag(tags, "operator")) then
        return "building", tag(tags, "building")
    end
    return nil
end

local function common_poi_columns()
    return {
        { column = "name", type = "text" },
        { column = "name_it", type = "text" },
        { column = "ref", type = "text" },
        { column = "operator", type = "text" },
        { column = "brand", type = "text" },
        { column = "addr_street", type = "text" },
        { column = "addr_housenumber", type = "text" },
        { column = "addr_city", type = "text" },
        { column = "phone", type = "text" },
        { column = "website", type = "text" },
        { column = "opening_hours", type = "text" },
        { column = "wheelchair", type = "text" },
        { column = "category", type = "text" },
        { column = "category_value", type = "text" },
        { column = "tags", type = "jsonb", not_null = true },
        { column = "osm_version", type = "int4" },
        { column = "osm_timestamp", type = "int8" },
    }
end

local function poi_values(object, category, category_value)
    local tags = object.tags
    return {
        name = tag(tags, "name"),
        name_it = tag(tags, "name:it"),
        ref = tag(tags, "ref"),
        operator = tag(tags, "operator"),
        brand = tag(tags, "brand"),
        addr_street = tag(tags, "addr:street"),
        addr_housenumber = tag(tags, "addr:housenumber"),
        addr_city = tag(tags, "addr:city"),
        phone = tag(tags, "phone"),
        website = tag(tags, "website"),
        opening_hours = tag(tags, "opening_hours"),
        wheelchair = tag(tags, "wheelchair"),
        category = category,
        category_value = category_value,
        tags = tags,
        osm_version = object.version,
        osm_timestamp = object.timestamp,
    }
end

local road_columns = {
    { column = "name", type = "text" },
    { column = "name_it", type = "text" },
    { column = "ref", type = "text" },
    { column = "highway", type = "text" },
    { column = "access", type = "text" },
    { column = "foot", type = "text" },
    { column = "bicycle", type = "text" },
    { column = "motor_vehicle", type = "text" },
    { column = "vehicle", type = "text" },
    { column = "oneway", type = "text" },
    { column = "junction", type = "text" },
    { column = "bridge", type = "text" },
    { column = "tunnel", type = "text" },
    { column = "layer", type = "text" },
    { column = "surface", type = "text" },
    { column = "service", type = "text" },
    { column = "maxspeed", type = "text" },
    { column = "lanes", type = "text" },
    { column = "width", type = "text" },
    { column = "tracktype", type = "text" },
    { column = "smoothness", type = "text" },
    { column = "wheelchair", type = "text" },
    { column = "incline", type = "text" },
    { column = "sidewalk", type = "text" },
    { column = "cycleway", type = "text" },
    { column = "footway", type = "text" },
    { column = "segregated", type = "text" },
    { column = "construction", type = "text" },
    { column = "route", type = "text" },
    { column = "tags", type = "jsonb", not_null = true },
    { column = "geom", type = "linestring", projection = srid, not_null = true },
    { column = "osm_version", type = "int4" },
    { column = "osm_timestamp", type = "int8" },
}

tables.osm_ways = osm2pgsql.define_table({
    name = "osm_ways",
    ids = { type = "way", id_column = "osm_id" },
    columns = road_columns,
})

tables.poi_nodes = osm2pgsql.define_table({
    name = "poi_nodes",
    ids = { type = "node", id_column = "osm_id" },
    columns = (function()
        local columns = common_poi_columns()
        columns[#columns + 1] = { column = "geom", type = "point", projection = srid, not_null = true }
        return columns
    end)(),
})

tables.poi_way_areas = osm2pgsql.define_table({
    name = "poi_way_areas",
    ids = { type = "way", id_column = "osm_id" },
    columns = (function()
        local columns = common_poi_columns()
        columns[#columns + 1] = { column = "geom", type = "geometry", projection = srid, not_null = true }
        return columns
    end)(),
})

tables.poi_relation_areas = osm2pgsql.define_table({
    name = "poi_relation_areas",
    ids = { type = "relation", id_column = "osm_id" },
    columns = (function()
        local columns = common_poi_columns()
        columns[#columns + 1] = { column = "geom", type = "geometry", projection = srid, not_null = true }
        return columns
    end)(),
})

function osm2pgsql.process_node(object)
    local category, category_value = poi_category(object.tags)
    if not category then
        return
    end
    local values = poi_values(object, category, category_value)
    values.geom = object:as_point()
    if not values.geom:is_null() then
        tables.poi_nodes:insert(values)
    end
end

function osm2pgsql.process_way(object)
    local tags = object.tags
    if tags.highway then
        local values = {
            name = tag(tags, "name"),
            name_it = tag(tags, "name:it"),
            ref = tag(tags, "ref"),
            highway = tag(tags, "highway"),
            access = tag(tags, "access"),
            foot = tag(tags, "foot"),
            bicycle = tag(tags, "bicycle"),
            motor_vehicle = tag(tags, "motor_vehicle"),
            vehicle = tag(tags, "vehicle"),
            oneway = tag(tags, "oneway"),
            junction = tag(tags, "junction"),
            bridge = tag(tags, "bridge"),
            tunnel = tag(tags, "tunnel"),
            layer = tag(tags, "layer"),
            surface = tag(tags, "surface"),
            service = tag(tags, "service"),
            maxspeed = tag(tags, "maxspeed"),
            lanes = tag(tags, "lanes"),
            width = tag(tags, "width"),
            tracktype = tag(tags, "tracktype"),
            smoothness = tag(tags, "smoothness"),
            wheelchair = tag(tags, "wheelchair"),
            incline = tag(tags, "incline"),
            sidewalk = tag(tags, "sidewalk"),
            cycleway = tag(tags, "cycleway"),
            footway = tag(tags, "footway"),
            segregated = tag(tags, "segregated"),
            construction = tag(tags, "construction"),
            route = tag(tags, "route"),
            tags = tags,
            osm_version = object.version,
            osm_timestamp = object.timestamp,
        }
        values.geom = object:as_linestring()
        if not values.geom:is_null() then
            tables.osm_ways:insert(values)
        end
    end

    local category, category_value = poi_category(tags)
    if category and object.is_closed then
        local values = poi_values(object, category, category_value)
        values.geom = object:as_polygon()
        if not values.geom:is_null() then
            tables.poi_way_areas:insert(values)
        end
    end
end

function osm2pgsql.process_relation(object)
    local category, category_value = poi_category(object.tags)
    if not category then
        return
    end
    local values = poi_values(object, category, category_value)
    values.geom = object:as_multipolygon()
    if not values.geom:is_null() then
        tables.poi_relation_areas:insert(values)
    end
end
