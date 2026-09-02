--[[----------------------------------------------------------------------------
HeadshotExportProvider.lua
Lightroom Classic Export Service Provider for Headshot Booth Delivery System
------------------------------------------------------------------------------]]

local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local LrErrors = import 'LrErrors'
local LrDialogs = import 'LrDialogs'
local LrHttp = import 'LrHttp'
local LrView = import 'LrView'
local LrTasks = import 'LrTasks'

local exportServiceProvider = {}

exportServiceProvider.hideSections = { 'exportLocation' }
exportServiceProvider.canExportToTemporaryLocation = true
exportServiceProvider.allowFileFormats = { 'JPEG' }
exportServiceProvider.allowColorSpaces = { 'sRGB' }
exportServiceProvider.canExportVideo = false

exportServiceProvider.exportPresetFields = {
    { key = 'deliveryService', default = 'HeadshotBooth' },
}

function exportServiceProvider.startDialog( propertyTable )
    propertyTable.LR_cantExportBecause = nil
    propertyTable.LR_format = "JPEG"
    propertyTable.LR_jpeg_quality = 0.85
    propertyTable.LR_export_colorSpace = "sRGB"
    propertyTable.LR_metadata_filter = "all"
    propertyTable.LR_embeddedMetadataOption = "all"
    propertyTable.LR_outputSharpeningOn = false
    propertyTable.LR_size_doConstrain = false
end

function exportServiceProvider.sectionsForTopOfDialog( _, propertyTable )
    local f = LrView.osFactory()
    return {
        {
            title = "Headshot Booth Delivery Service",
            f:row {
                f:static_text {
                    title = "Keepers will be automatically uploaded to the attendee's private Zenfolio gallery\nand a personalized notification email will be dispatched via Gmail.",
                    fill_horizontal = 1,
                    height_in_lines = 2,
                },
            },
        },
    }
end

function exportServiceProvider.processRenderedPhotos( functionContext, exportContext )
    local exportSession = exportContext.exportSession
    local nPhotos = exportSession:countRenditions()

    local progressScope = exportContext:configureProgress {
        title = nPhotos > 1
            and string.format( "Delivering %d headshot keepers...", nPhotos )
            or "Delivering headshot keeper...",
    }

    local failures = {}
    local successCount = 0
    local lastGalleryUrl = ""
    local lastAttendeeName = ""

    local apiUrl = "http://localhost:8000/api/deliver"

    for _, rendition in exportContext:renditions{ stopIfCanceled = true } do
        if progressScope:isCanceled() then break end

        local success, pathOrMessage = rendition:waitForRender()
        if success then
            local filePath = pathOrMessage
            local filename = LrPathUtils.leafName( filePath )

            -- Prepare multipart payload
            local mimeChunks = {
                {
                    name = "file_path",
                    value = filePath,
                },
                {
                    name = "file",
                    fileName = filename,
                    filePath = filePath,
                    contentType = "image/jpeg",
                },
            }

            local responseBody, responseHeaders = LrHttp.postMultipart( apiUrl, mimeChunks, 45 )

            if responseHeaders and responseHeaders.status == 200 then
                successCount = successCount + 1
                if responseBody then
                    -- Extract attendee_name and gallery_url if present in JSON
                    local attName = responseBody:match('"attendee_name"%s*:%s*"([^"]+)"')
                    local galUrl = responseBody:match('"gallery_url"%s*:%s*"([^"]+)"')
                    if attName then lastAttendeeName = attName end
                    if galUrl then lastGalleryUrl = galUrl end
                end
            else
                local errDetail = responseBody or "Local delivery server not reachable. Ensure run_booth.bat is running at localhost:8000."
                table.insert( failures, string.format( "%s: %s", filename, errDetail ) )
            end
        else
            table.insert( failures, string.format( "Render failed: %s", tostring( pathOrMessage ) ) )
        end
    end

    if #failures > 0 then
        local msg = string.format( "%d photo(s) failed delivery.\n\nMake sure the Headshot Booth app is running at localhost:8000.", #failures )
        LrDialogs.message( "Headshot Delivery Error", table.concat( failures, "\n" ), "critical" )
    else
        if lastAttendeeName ~= "" then
            local bezelMsg = string.format( "Delivered to %s! 🚀", lastAttendeeName )
            LrDialogs.showBezel( bezelMsg, 4 )
        else
            LrDialogs.showBezel( string.format( "Delivered %d Headshot Keeper(s) Successfully!", successCount ), 4 )
        end
    end
end

return exportServiceProvider
