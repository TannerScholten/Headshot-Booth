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

-- Export Dialog Settings & Presets
exportServiceProvider.hideSections = { 'exportLocation', 'fileNaming' }
exportServiceProvider.allowFileFormats = { 'JPEG' }
exportServiceProvider.allowColorSpaces = { 'sRGB' }
exportServiceProvider.canExportVideo = false

exportServiceProvider.exportPresetProperties = {
    LR_format = "JPEG",
    LR_jpeg_quality = 0.85,
    LR_jpeg_useLimitSize = false,
    LR_outputSharpeningOn = false,
    LR_size_doConstrain = false,
    LR_metadata_filter = "all",
    LR_embeddedMetadataOption = "all",
}

function exportServiceProvider.sectionsForTopOfDialog( f, propertyTable )
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

            local responseBody, responseHeaders = LrHttp.postMultipart( apiUrl, mimeChunks )

            if responseHeaders and responseHeaders.status == 200 then
                successCount = successCount + 1
            else
                local errDetail = responseBody or "Local delivery server not reachable. Ensure run_booth.bat is running."
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
        LrDialogs.showBezel( string.format( "Delivered %d Headshot(s) Successfully!", successCount ), 4 )
    end
end

return exportServiceProvider
