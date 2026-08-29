return {
    LrSdkVersion = 3.0,
    LrSdkMinimumVersion = 2.0,
    LrToolkitIdentifier = 'com.tannerscholten.headshotbooth',
    LrPluginName = 'Headshot Booth & Zenfolio Delivery',
    LrPluginInfoUrl = 'https://www.tannereli.com',

    -- Custom Export Service Provider
    LrExportServiceProvider = {
        title = "Headshot Booth Delivery",
        file = 'HeadshotExportProvider.lua',
    },

    -- Custom Metadata Definition
    LrMetadataProvider = 'HeadshotMetadataDefinition.lua',

    -- Metadata Tagset in Library Panel
    LrMetadataTagsetFactory = {
        'HeadshotMetadataTagset.lua',
    },

    VERSION = { major=1, minor=0, revision=0, build="20260828", },
}
