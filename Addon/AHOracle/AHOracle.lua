-- AHOracle.lua : single-file addon
local addonName, ns = ...
local A = _G.AHOracle or {}
_G.AHOracle = A

A.name    = "AHOracle"
A.version = "1.3.0"

A.STATE = { IDLE = 0, SCANNING = 1, COMPLETE = 2 }

A.state       = A.STATE.IDLE
A.progress    = 0
A.scanMode    = nil
A.scanDetail  = ""
A.lastStats   = nil

local ZONE_FACTION = {
    ["Orgrimmar"]       = "Horde",
    ["Undercity"]       = "Horde",
    ["Thunder Bluff"]   = "Horde",
    ["Stormwind City"]  = "Alliance",
    ["Ironforge"]       = "Alliance",
    ["Darnassus"]       = "Alliance",
    ["Gadgetzan"]       = "Neutral",
    ["Everlook"]        = "Neutral",
    ["Booty Bay"]       = "Neutral",
}

function A:DetectFaction()
    local zone = tostring(GetRealZoneText() or "")
    local sub  = tostring(GetSubZoneText()  or "")
    if ZONE_FACTION[zone] then return tostring(ZONE_FACTION[zone]) end
    if ZONE_FACTION[sub]  then return tostring(ZONE_FACTION[sub])  end
    return nil
end

function A:CurrentZone()
    local z = tostring(GetRealZoneText() or "?")
    local s = GetSubZoneText()
    if s and s ~= "" and s ~= z then return tostring(z) .. " / " .. tostring(s) end
    return tostring(z)
end

local function Print(msg)
    DEFAULT_CHAT_FRAME:AddMessage("|cff00ccff[AHOracle]|r " .. tostring(msg))
end
A.Print = Print

local function Defaults()
    return {
        version = 1,
        scans = { Alliance = nil, Horde = nil, Neutral = nil },
        fragments = {
            Alliance = { listings = {}, last_updated = 0 },
            Horde    = { listings = {}, last_updated = 0 },
            Neutral  = { listings = {}, last_updated = 0 },
        },
        settings = {
            passiveScan         = true,
            autoOpen            = true,
            hideMinimapButton   = false,
            staleHours          = 24,
            maxFragmentListings = 5000,
        },
        diagnostics = {
            lastFaction     = nil,
            lastFullScanAt  = 0,
            lastFragmentAt  = 0,
        },
    }
end

function A:InitDB()
    if type(AHOracleDB) ~= "table" then AHOracleDB = Defaults() end
    local d = Defaults()
    AHOracleDB.version = AHOracleDB.version or 1

    if type(AHOracleDB.scans) ~= "table" then AHOracleDB.scans = d.scans end

    if type(AHOracleDB.fragments) ~= "table" then AHOracleDB.fragments = d.fragments end
    for _, k in ipairs({"Alliance","Horde","Neutral"}) do
        local f = AHOracleDB.fragments[k]
        if type(f) ~= "table" then
            AHOracleDB.fragments[k] = { listings = {}, last_updated = 0 }
        else
            f.listings     = f.listings or {}
            f.last_updated = f.last_updated or 0
        end
    end

    if type(AHOracleDB.settings) ~= "table" then AHOracleDB.settings = d.settings end
    for k, v in pairs(d.settings) do
        if AHOracleDB.settings[k] == nil then AHOracleDB.settings[k] = v end
    end

    if type(AHOracleDB.diagnostics) ~= "table" then AHOracleDB.diagnostics = d.diagnostics end
    for k, v in pairs(d.diagnostics) do
        if AHOracleDB.diagnostics[k] == nil then AHOracleDB.diagnostics[k] = v end
    end

    self.db = AHOracleDB
end

function A:GetScan(faction)     return self.db and self.db.scans[faction] end
function A:GetFragments(faction)
    return self.db and self.db.fragments[faction] or { listings = {}, last_updated = 0 }
end

function A:HoursSince(ts)
    if not ts or ts == 0 then return nil end
    return (time() - ts) / 3600
end

-- =========================================================================
-- Scan Engine v9.0 — Dynamic Category Scanning
-- =========================================================================
local PAGE_SIZE    = 50
local PAGE_TIMEOUT = 20
local CHUNK_SIZE   = 10

local scan = {
    active        = false,
    faction       = nil,
    zone          = nil,
    categoryIndex = 1,      -- Which category we are on
    currentPage   = 0,
    pendingPage   = -1,
    totalPages    = 1,
    listings      = {},
    seen          = {},
    startTime     = 0,
    lastSentAt    = 0,
    pagesReceived = 0,
    retries       = 0,
    strays        = 0,
    numBatch      = 0,
    processIndex  = 0,
    totalFound    = 0,
    waitingInitial = false,
    categories    = {},     -- Will hold the exact classes from the Blizzard API
}
A.scan = scan

local DURATION_HOURS = { [1]=24, [2]=8, [3]=2, [4]=2, [5]=2 }

local function ReadListing(i)
    local name, _, count, _, _, _, _, _, _, buyoutPrice, _, _, _, owner = GetAuctionItemInfo("list", i)
    
    if not name or not buyoutPrice or buyoutPrice <= 0 or not count or count <= 0 then
        return nil
    end
    
    local link = GetAuctionItemLink("list", i)
    if not link then return nil end
    local itemID = tonumber(link:match("item:(%d+)"))
    if not itemID then return nil end

    local durCode = GetAuctionItemTimeLeft("list", i) or 0

    return {
        item_id           = itemID,
        item_name         = tostring(name),
        seller            = tostring(owner or "Unknown"),
        stack_size        = count,
        unit_buyout_price = math.floor(buyoutPrice / count),
        duration_hours    = DURATION_HOURS[durCode] or 0,
    }
end

--[[
  COMMENTED OUT: The Single-Page "All Items" Scan.
  This was working, but Blizzard hard-caps query results at ~8,500 items (170 pages).
  We keep it here for reference if we ever want to do a fast "commodities only" scan.

function A:StartFullScan_Old()
    if scan.active then
        self:Print("A scan is already running.")
        return
    end

    local faction = self:DetectFaction()
    if not faction then
        self:Print("|cffff5555Could not detect faction.|r Open the AH in a known city.")
        return
    end

    scan.active        = true
    scan.faction       = tostring(faction)
    scan.zone          = tostring(self:CurrentZone())
    scan.currentPage   = 0
    scan.pendingPage   = -1
    scan.totalPages    = 1
    scan.listings      = {}
    scan.seen          = {}
    scan.startTime     = time()
    scan.lastSentAt    = GetTime()
    scan.pagesReceived = 0
    scan.retries       = 0
    scan.strays        = 0
    scan.totalFound    = 0

    self.state      = self.STATE.SCANNING
    self.progress   = 1
    self.scanMode   = "FULL"
    self.scanDetail = "Starting full AH scan..."

    self:UpdateUI()
    self:_SendPage()
end
]]

-- =========================================================================
-- NEW: Category Scan (Bypasses the 8,500 item limit)
-- =========================================================================
function A:StartFullScan()
    if scan.active then
        self:Print("A scan is already running.")
        return
    end

    local faction = self:DetectFaction()
    if not faction then
        self:Print("|cffff5555Could not detect faction.|r Open the AH in a known city.")
        return
    end

    -- Dynamically build the category list from Blizzard's API
    scan.categories = { GetAuctionItemClasses() }
    if #scan.categories == 0 then
        self:Print("|cffff5555Could not load AH categories.|r")
        return
    end

    scan.active        = true
    scan.faction       = tostring(faction)
    scan.zone          = tostring(self:CurrentZone())
    scan.categoryIndex = 1
    scan.currentPage   = 0
    scan.pendingPage   = -1
    scan.totalPages    = 1
    scan.listings      = {}
    scan.seen          = {}
    scan.startTime     = time()
    scan.lastSentAt    = GetTime()
    scan.pagesReceived = 0
    scan.retries       = 0
    scan.strays        = 0
    scan.totalFound    = 0

    self.state      = self.STATE.SCANNING
    self.progress   = 0
    self.scanMode   = "FULL"

    self:SelectCategory(1)
end

function A:SelectCategory(index)
    if index > #scan.categories then
        self:_FinishScan()
        return
    end

    scan.categoryIndex = index
    scan.currentPage = 0
    scan.totalPages = 1
    scan.pagesReceived = 0
    scan.waitingInitial = true
    scan.pendingPage = 0
    scan.lastSentAt = GetTime()
    scan.retries = 0
    
    local catName = tostring(scan.categories[index])
    
    -- Override the name for the last category (Miscellaneous) if needed
    if index == #scan.categories and catName == "" then catName = "Miscellaneous" end

    self.scanDetail = "Scanning: " .. catName
    self.progress = math.floor(((index - 1) / #scan.categories) * 100)
    self:UpdateUI()

    -- Send the query with the specific category index
    QueryAuctionItems("", nil, nil, 0, nil, nil, false, false, index)

    local expected = 0
    C_Timer.After(PAGE_TIMEOUT, function()
        if not scan.active then return end
        if scan.pendingPage ~= expected then return end
        if scan.retries < 3 then
            scan.retries = scan.retries + 1
            self.scanDetail = string.format("%s timeout, retry %d/3", catName, scan.retries)
            self:UpdateUI()
            A:SelectCategory(index)
        else
            self:Print("|cffff5555Category "..catName.." failed to load. Skipping.|r")
            A:SelectCategory(index + 1)
        end
    end)
end

function A:CancelScan()
    if not scan.active then return end
    scan.active = false
    scan.pendingPage = -1
    self.state = self.STATE.IDLE
    self.progress = 0
    self.scanDetail = ""
    self:Print("Scan cancelled.")
    self:UpdateUI()
end

function A:_SendPage()
    if not scan.active then return end

    local now = GetTime()

    if not CanSendAuctionQuery() then
        if now - scan.lastSentAt > PAGE_TIMEOUT then
            if scan.retries < 3 then
                scan.retries = scan.retries + 1
                self.scanDetail = string.format("Throttle timeout, retry %d/3", scan.retries)
                self:UpdateUI()
                scan.lastSentAt = now
            else
                self:Print("|cffff5555AH throttle failed — aborting scan.|r")
                self:CancelScan()
                return
            end
        end
        C_Timer.After(0.2, function() A:_SendPage() end)
        return
    end

    scan.pendingPage = scan.currentPage
    scan.lastSentAt  = GetTime()
    scan.retries     = 0
    
    -- Pass the category index as the 9th argument (filter)
    QueryAuctionItems("", nil, nil, scan.currentPage, nil, nil, false, false, scan.categoryIndex)

    local expected = scan.pendingPage
    C_Timer.After(PAGE_TIMEOUT, function()
        if not scan.active        then return end
        if scan.pendingPage ~= expected then return end
        if scan.retries < 3 then
            scan.retries = scan.retries + 1
            self.scanDetail = string.format("Page %d timed out, retry %d/3", expected, scan.retries)
            self:UpdateUI()
            A:_SendPage()
        else
            self:Print(("|cffff5555Page %d failed after 3 retries — aborting scan.|r"):format(expected))
            A:CancelScan()
        end
    end)
end

function A:OnScanPage()
    if not scan.active        then return end
    if scan.pendingPage < 0   then return end

    local respondedPage = scan.pendingPage
    scan.pendingPage = -1

    local numBatch, total = GetNumAuctionItems("list")
    numBatch = numBatch or 0
    total    = total or 0
    if total <= 0 or total > 500000 then total = numBatch end

    if scan.waitingInitial then
        scan.waitingInitial = false
        scan.totalPages = math.max(1, math.ceil(total / PAGE_SIZE))
        scan.totalFound = total
        
        local catName = tostring(scan.categories[scan.categoryIndex] or "")
        if catName == "" then catName = "Miscellaneous" end
        
        if total > 0 then
            self.scanDetail = string.format("%s: %d listings (%d pages)", 
                catName, total, scan.totalPages)
            self:UpdateUI()
        end
    end

    -- Stray filter & Empty Page handling
    if respondedPage < scan.totalPages - 1 and numBatch < (PAGE_SIZE - 10) then
        scan.strays = scan.strays + 1
        if scan.strays > 3 then
            scan.strays = 0
            scan.numBatch = 0
            scan.processIndex = 1
        else
            A:_SendPage()
            return
        end
    end

    scan.numBatch = numBatch
    scan.processIndex = 1
    scan.retries = 0

    local function ProcessChunk()
        if not scan.active then return end
        
        local limit = math.min(scan.processIndex + CHUNK_SIZE - 1, scan.numBatch)
        
        for i = scan.processIndex, limit do
            local l = ReadListing(i)
            if l then
                local key = string.format("%d|%s|%d|%d",
                    l.item_id, tostring(l.seller or ""), l.stack_size, l.unit_buyout_price)
                if not scan.seen[key] then
                    scan.seen[key] = true
                    table.insert(scan.listings, l)
                end
            end
        end
        
        scan.processIndex = limit + 1
        
        if scan.processIndex <= scan.numBatch then
            C_Timer.After(0, ProcessChunk)
        else
            scan.pagesReceived = scan.pagesReceived + 1
            
            local catName = tostring(scan.categories[scan.categoryIndex] or "")
            if catName == "" then catName = "Miscellaneous" end

            self.scanDetail = string.format("%s: Page %d/%d", 
                catName, scan.pagesReceived, scan.totalPages)
            self:UpdateUI()

            if scan.numBatch >= PAGE_SIZE and respondedPage < scan.totalPages - 1 then
                scan.currentPage = respondedPage + 1
                A:_SendPage()
            else
                -- Move to the next category
                self:SelectCategory(scan.categoryIndex + 1)
            end
        end
    end

    ProcessChunk()
end

function A:_FinishScan()
    scan.active = false
    self.progress = 100
    self.state = self.STATE.COMPLETE
    self.scanDetail = ""

    local faction = scan.faction

    self.db.scans[faction] = {
        scan_timestamp = time(),
        faction        = tostring(faction),
        zone           = tostring(scan.zone),
        listings       = scan.listings,
    }
    self.db.fragments[faction] = { listings = {}, last_updated = 0 }

    self.db.diagnostics.lastFaction    = tostring(faction)
    self.db.diagnostics.lastFullScanAt = time()

    self.lastStats = {
        faction   = tostring(faction),
        listings  = #scan.listings,
        seconds   = math.max(1, time() - scan.startTime),
    }

    self:Print(("Scan complete: %d unique listings for %s (%ds)")
        :format(#scan.listings, tostring(faction), self.lastStats.seconds))

    self:UpdateUI()
end

-- =========================================================================
-- Passive Fragment Scanning (Fast, Name-less, Deduplicated)
-- =========================================================================
local FRAGMENT_COOLDOWN = 5
local lastSweep = 0
local recentFragments = {}

function A:CaptureFragment()
    if not self.db or not self.db.settings.passiveScan then return end
    if A.scan and A.scan.active then return end
    if GetTime() - lastSweep < FRAGMENT_COOLDOWN then return end

    local faction = self:DetectFaction()
    if not faction then return end

    local numBatch = GetNumAuctionItems("list")
    if not numBatch or numBatch == 0 then return end

    lastSweep = GetTime()

    local bucket = self.db.fragments[faction]
    local listings = bucket.listings
    local now = time()
    local added = 0

    for i = 1, numBatch do
        local name, _, count, _, _, _, _, _, _, buyoutPrice = GetAuctionItemInfo("list", i)
        local link = GetAuctionItemLink("list", i)
        local itemID = link and tonumber(link:match("item:(%d+)"))

        if itemID and buyoutPrice and buyoutPrice > 0 and count and count > 0 then
            local unit_price = math.floor(buyoutPrice / count)
            local key = string.format("%d|%d|%d", itemID, count, unit_price)
            local lastSeen = recentFragments[key]
            
            if not lastSeen or (now - lastSeen) > 600 then
                recentFragments[key] = now
                table.insert(listings, {
                    item_id           = itemID,
                    stack_size        = count,
                    unit_buyout_price = unit_price,
                    observed_at       = now,
                })
                added = added + 1
            end
        end
    end

    if added > 0 then
        local cap = self.db.settings.maxFragmentListings or 5000
        while #listings > cap do table.remove(listings, 1) end

        bucket.last_updated = now
        self.db.diagnostics.lastFragmentAt = now
        self:UpdateUI()
    end
end

-- =========================================================================
-- Main UI
-- =========================================================================
local frame

local function ApplyBackdrop(f)
    f:SetBackdrop({
        bgFile   = "Interface\\DialogFrame\\UI-DialogBox-Background-Dark",
        edgeFile = "Interface\\DialogFrame\\UI-DialogBox-Border",
        tile = true, tileSize = 32, edgeSize = 32,
        insets = { left = 8, right = 8, top = 8, bottom = 8 },
    })
end

local function Header(f, text, x, y)
    local fs = f:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    fs:SetPoint("TOPLEFT", x, y)
    fs:SetText(text)
    fs:SetTextColor(1, 0.82, 0)
    return fs
end

function A:CreateUI()
    if frame then return frame end

    local f = CreateFrame("Frame", "AHOracleFrame", UIParent, "BackdropTemplate")
    f:SetSize(520, 540)
    f:SetPoint("CENTER")
    f:SetFrameStrata("DIALOG")
    f:SetMovable(true); f:EnableMouse(true)
    f:RegisterForDrag("LeftButton")
    f:SetScript("OnDragStart", f.StartMoving)
    f:SetScript("OnDragStop",  f.StopMovingOrSizing)
    f:SetClampedToScreen(true)
    ApplyBackdrop(f)
    f:Hide()

    local title = f:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
    title:SetPoint("TOP", 0, -16)
    title:SetText("AHOracle")
    title:SetTextColor(1, 0.82, 0)

    local close = CreateFrame("Button", nil, f, "UIPanelCloseButton")
    close:SetPoint("TOPRIGHT", -4, -4)

    local warnText = f:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    warnText:SetPoint("TOP", 0, -40)
    warnText:SetTextColor(1, 0.2, 0.2)
    warnText:SetJustifyH("CENTER")
    warnText:Hide()
    f.warnText = warnText

    Header(f, "Location", 24, -64)

    local locText = f:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    locText:SetPoint("TOPLEFT", 32, -84)
    locText:SetWidth(456)
    locText:SetJustifyH("LEFT")
    f.locText = locText

    Header(f, "Full Scan", 24, -120)

    local status = f:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    status:SetPoint("TOPLEFT", 32, -140)
    status:SetWidth(456)
    status:SetJustifyH("LEFT")
    status:SetText("Ready.")
    f.statusText = status

    local detailText = f:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    detailText:SetPoint("TOPLEFT", 32, -158)
    detailText:SetWidth(456)
    detailText:SetJustifyH("LEFT")
    detailText:SetTextColor(0.8, 0.8, 0.8)
    f.scanDetailText = detailText

    local bar = CreateFrame("StatusBar", nil, f)
    bar:SetSize(456, 22)
    bar:SetPoint("TOPLEFT", 32, -180)
    bar:SetStatusBarTexture("Interface\\TargetingFrame\\UI-StatusBar")
    bar:GetStatusBarTexture():SetHorizTile(false)
    bar:SetMinMaxValues(0, 100)
    bar:SetValue(0)
    bar:SetStatusBarColor(0.2, 0.7, 1.0)

    local bg = bar:CreateTexture(nil, "BACKGROUND")
    bg:SetAllPoints(); bg:SetColorTexture(0.1, 0.1, 0.1, 0.8)

    local barText = bar:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    barText:SetPoint("CENTER")
    barText:SetText("0%")
    bar.barText = barText
    f.progressBar = bar

    local scanBtn = CreateFrame("Button", nil, f, "UIPanelButtonTemplate")
    scanBtn:SetSize(150, 28)
    scanBtn:SetPoint("TOPLEFT", 32, -212)
    scanBtn:SetText("Scan All")
    scanBtn:SetScript("OnClick", function() A:StartFullScan() end)
    f.scanBtn = scanBtn

    local cancelBtn = CreateFrame("Button", nil, f, "UIPanelButtonTemplate")
    cancelBtn:SetSize(120, 28)
    cancelBtn:SetPoint("LEFT", scanBtn, "RIGHT", 10, 0)
    cancelBtn:SetText("Cancel")
    cancelBtn:SetScript("OnClick", function() A:CancelScan() end)
    f.cancelBtn = cancelBtn

    Header(f, "Passive Fragment Data", 24, -258)

    local fragText = f:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    fragText:SetPoint("TOPLEFT", 32, -278)
    fragText:SetWidth(456)
    fragText:SetJustifyH("LEFT")
    fragText:SetText("No fragments yet.")
    f.fragText = fragText

    local passiveCheck = CreateFrame("CheckButton", nil, f,
        "InterfaceOptionsCheckButtonTemplate")
    passiveCheck:SetPoint("TOPLEFT", 24, -300)
    passiveCheck.Text:SetText("Enable passive fragment scanning")
    passiveCheck:SetScript("OnClick", function(self)
        A.db.settings.passiveScan = self:GetChecked() and true or false
    end)
    f.passiveCheck = passiveCheck

    local autoOpenCheck = CreateFrame("CheckButton", nil, f,
        "InterfaceOptionsCheckButtonTemplate")
    autoOpenCheck:SetPoint("TOPLEFT", 24, -324)
    autoOpenCheck.Text:SetText("Auto-open this window when the AH opens")
    autoOpenCheck:SetScript("OnClick", function(self)
        A.db.settings.autoOpen = self:GetChecked() and true or false
    end)
    f.autoOpenCheck = autoOpenCheck

    local minimapCheck = CreateFrame("CheckButton", nil, f,
        "InterfaceOptionsCheckButtonTemplate")
    minimapCheck:SetPoint("TOPLEFT", 24, -348)
    minimapCheck.Text:SetText("Show minimap button")
    minimapCheck:SetScript("OnClick", function(self)
        local show = self:GetChecked() and true or false
        A.db.settings.hideMinimapButton = not show
        A:UpdateMinimapButton()
    end)
    f.minimapCheck = minimapCheck

    Header(f, "Scan Summary", 24, -384)

    local stats = f:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    stats:SetPoint("TOPLEFT", 32, -404)
    stats:SetWidth(456)
    stats:SetJustifyH("LEFT")
    stats:SetText("")
    f.statsText = stats

    local clearBtn = CreateFrame("Button", nil, f, "UIPanelButtonTemplate")
    clearBtn:SetSize(160, 24)
    clearBtn:SetPoint("BOTTOMLEFT", 24, 16)
    clearBtn:SetText("Clear All Data")
    clearBtn:SetScript("OnClick", function()
        for _, k in ipairs({"Alliance","Horde","Neutral"}) do
            AHOracleDB.scans[k]     = nil
            AHOracleDB.fragments[k] = { listings = {}, last_updated = 0 }
        end
        AHOracleDB.diagnostics.lastFullScanAt  = 0
        AHOracleDB.diagnostics.lastFragmentAt  = 0
        AHOracleDB.diagnostics.lastFaction     = nil
        A:Print("All scan data cleared.")
        A:UpdateUI()
    end)

    local refreshBtn = CreateFrame("Button", nil, f, "UIPanelButtonTemplate")
    refreshBtn:SetSize(120, 24)
    refreshBtn:SetPoint("LEFT", clearBtn, "RIGHT", 8, 0)
    refreshBtn:SetText("Refresh")
    refreshBtn:SetScript("OnClick", function() A:UpdateUI() end)

    frame = f
    return f
end

function A:ToggleFrame()
    local f = self:CreateUI()
    if f:IsShown() then f:Hide() else f:Show(); self:UpdateUI() end
end

function A:ShowFrame()
    local f = self:CreateUI()
    f:Show()
    self:UpdateUI()
end

function A:UpdateUI()
    local f = frame
    if not f or not self.db then return end

    local faction = self:DetectFaction()
    local zone    = self:CurrentZone()
    if faction then
        f.locText:SetText(string.format("Zone: %s   |cff888888|   Faction: |cffffff78%s|r",
            tostring(zone), tostring(faction)))
    else
        f.locText:SetText(string.format("Zone: %s   |cffff8888|   Faction: unknown|r",
            tostring(zone)))
    end

    if self.state == self.STATE.SCANNING then
        f.statusText:SetText(string.format("Scanning... %d%%", self.progress or 0))
        f.scanDetailText:SetText(tostring(self.scanDetail or ""))
    elseif self.state == self.STATE.COMPLETE then
        f.statusText:SetText("Scan complete.")
        f.scanDetailText:SetText("")
    else
        f.scanDetailText:SetText("")
        if faction then
            local hrs = self:HoursSince(self.db.diagnostics.lastFullScanAt)
            if not self.db.scans[faction] or not self.db.scans[faction].scan_timestamp then
                f.statusText:SetText("|cffffcc55No full scan recorded for this faction yet.|r")
            elseif hrs and hrs >= (self.db.settings.staleHours or 24) then
                f.statusText:SetText(string.format(
                    "|cffffcc55Data is stale (%.1fh old). A fresh scan is recommended.|r", hrs))
            else
                f.statusText:SetText(string.format("Ready. Last scan for %s: %.1fh ago.",
                    tostring(faction), hrs or 0))
            end
        else
            f.statusText:SetText("Ready.")
        end
    end

    f.progressBar:SetValue(self.progress or 0)
    f.progressBar.barText:SetText(string.format("%d%%", self.progress or 0))

    if faction then
        local frag = self:GetFragments(faction)
        local n   = #frag.listings
        local hrs = self:HoursSince(frag.last_updated)
        if n == 0 then
            f.fragText:SetText("No fragments captured for " .. tostring(faction) .. " yet.")
        elseif hrs then
            f.fragText:SetText(string.format(
                "%d fragment listings captured for %s (last: %.1fh ago).", n, tostring(faction), hrs))
        else
            f.fragText:SetText(string.format("%d fragment listings captured for %s.", n, tostring(faction)))
        end
    else
        f.fragText:SetText("Cannot detect faction from current location.")
    end

    f.passiveCheck:SetChecked(self.db.settings.passiveScan)
    f.autoOpenCheck:SetChecked(self.db.settings.autoOpen)
    f.minimapCheck:SetChecked(not self.db.settings.hideMinimapButton)

    local lines = {}
    for _, k in ipairs({"Alliance","Horde","Neutral"}) do
        local s = self.db.scans[k]
        if s and s.scan_timestamp then
            local ago = self:HoursSince(s.scan_timestamp)
            table.insert(lines, string.format("%-9s: %d listings  (%s ago)",
                tostring(k), #s.listings, string.format("%.1fh", ago or 0)))
        else
            table.insert(lines, string.format("%-9s: —", tostring(k)))
        end
    end
    f.statsText:SetText(table.concat(lines, "\n"))
end

-- =========================================================================
-- AH Tab
-- =========================================================================
local tab

local function BuildTab()
    if tab then return end
    if not AuctionFrame or not AuctionsTab then return end

    tab = CreateFrame("Button", "AHOracleTab", AuctionFrame)
    tab:SetSize(96, 32)
    tab:SetPoint("LEFT", AuctionsTab, "RIGHT", 4, 0)
    tab:SetFrameLevel(AuctionFrame:GetFrameLevel() + 2)

    local bg = tab:CreateTexture(nil, "BACKGROUND")
    bg:SetAllPoints(); bg:SetColorTexture(0.12, 0.12, 0.18, 0.92)

    local border = tab:CreateTexture(nil, "BORDER")
    border:SetAllPoints(); border:SetColorTexture(0.35, 0.35, 0.45, 0.9)

    local text = tab:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    text:SetPoint("CENTER")
    text:SetText("AHOracle")
    text:SetTextColor(1, 0.82, 0)

    tab:SetScript("OnClick", function() A:ShowFrame() end)

    tab:SetScript("OnEnter", function(self)
        if not self.hl then
            self.hl = self:CreateTexture(nil, "HIGHLIGHT")
            self.hl:SetAllPoints()
            self.hl:SetColorTexture(0.3, 0.3, 0.45, 0.55)
        end
    end)
end

-- =========================================================================
-- Minimap Button
-- =========================================================================
local minimapBtn

local function CreateMinimapButton()
    if minimapBtn then return minimapBtn end

    local btn = CreateFrame("Button", "AHOracleMinimapButton", Minimap)
    btn:SetSize(32, 32)
    btn:SetFrameStrata("MEDIUM")
    btn:SetFrameLevel(8)
    btn:RegisterForClicks("LeftButtonUp")
    btn:RegisterForDrag("LeftButton")
    btn:SetMovable(true)
    btn:SetClampedToScreen(true)

    local bg = btn:CreateTexture(nil, "BACKGROUND")
    bg:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder")
    bg:SetSize(52, 52)
    bg:SetPoint("CENTER", btn, "CENTER", 0, 0)

    local icon = btn:CreateTexture(nil, "ARTWORK")
    icon:SetTexture("Interface\\Icons\\INV_Misc_Coin_02")
    icon:SetSize(20, 20)
    icon:SetPoint("CENTER")
    icon:SetTexCoord(0.05, 0.95, 0.05, 0.95)
    btn.icon = icon

    local angle  = math.rad(45)
    local radius = 80
    btn:SetPoint("CENTER", Minimap, "CENTER",
        math.cos(angle) * radius, math.sin(angle) * radius)

    btn:SetScript("OnDragStart", function(self)
        self:SetScript("OnUpdate", function()
            local mx, my = Minimap:GetCenter()
            local cx, cy = GetCursorPosition()
            local scale  = Minimap:GetEffectiveScale()
            cx, cy = cx / scale, cy / scale
            local angle  = math.atan2(cy - my, cx - mx)
            local r      = 80
            self:ClearAllPoints()
            self:SetPoint("CENTER", Minimap, "CENTER",
                math.cos(angle) * r, math.sin(angle) * r)
        end)
    end)
    btn:SetScript("OnDragStop", function(self)
        self:SetScript("OnUpdate", nil)
    end)

    btn:SetScript("OnClick", function() A:ToggleFrame() end)

    btn:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_LEFT")
        GameTooltip:AddLine("AHOracle")
        GameTooltip:AddLine("Left-click: Open window", 1, 1, 1)
        GameTooltip:AddLine("Drag: Move button",      0.7, 0.7, 0.7)
        GameTooltip:Show()
    end)
    btn:SetScript("OnLeave", function() GameTooltip:Hide() end)

    minimapBtn = btn
    return btn
end

function A:UpdateMinimapButton()
    if not self.db then return end
    local btn = CreateMinimapButton()
    if self.db.settings.hideMinimapButton then btn:Hide() else btn:Show() end
end

-- =========================================================================
-- Events
-- =========================================================================
local boot = CreateFrame("Frame")
boot:RegisterEvent("ADDON_LOADED")
boot:SetScript("OnEvent", function(_, event, name)
    if event == "ADDON_LOADED" and name == addonName then
        A:InitDB()
        Print("v" .. A.version .. " loaded.  |cffffff78/aho|r to open.")
        A:UpdateMinimapButton()
    end
end)

local scanEvents = CreateFrame("Frame")
scanEvents:RegisterEvent("AUCTION_ITEM_LIST_UPDATE")
scanEvents:RegisterEvent("AUCTION_HOUSE_SHOW")
scanEvents:RegisterEvent("AUCTION_HOUSE_CLOSED")
scanEvents:SetScript("OnEvent", function(_, event)
    if event == "AUCTION_ITEM_LIST_UPDATE" then
        if A.scan and A.scan.active then
            A:OnScanPage()
        else
            A:CaptureFragment()
        end
    elseif event == "AUCTION_HOUSE_SHOW" then
        if A.db and A.db.settings.autoOpen then A:ShowFrame() end
        A:UpdateUI()
    elseif event == "AUCTION_HOUSE_CLOSED" then
        if A.scan and A.scan.active then A:CancelScan() end
        if _G.AHOracleFrame and _G.AHOracleFrame:IsShown() then
            _G.AHOracleFrame:Hide()
        end
    end
end)

local tabEvents = CreateFrame("Frame")
tabEvents:RegisterEvent("ADDON_LOADED")
tabEvents:RegisterEvent("AUCTION_HOUSE_SHOW")
tabEvents:SetScript("OnEvent", function(_, event)
    if event == "ADDON_LOADED" then
        C_Timer.After(1, BuildTab)
    elseif event == "AUCTION_HOUSE_SHOW" then
        BuildTab()
    end
end)

-- Hook to catch aux/TSM closing by hiding AuctionFrame
local hookFrame = CreateFrame("Frame")
hookFrame:RegisterEvent("ADDON_LOADED")
hookFrame:RegisterEvent("AUCTION_HOUSE_SHOW")
hookFrame:SetScript("OnEvent", function(_, event, name)
    if event == "ADDON_LOADED" and name ~= addonName then return end
    if AuctionFrame and not AuctionFrame.__ahoHook then
        AuctionFrame.__ahoHook = true
        AuctionFrame:HookScript("OnHide", function()
            if A.scan and A.scan.active then A:CancelScan() end
            if _G.AHOracleFrame and _G.AHOracleFrame:IsShown() then
                _G.AHOracleFrame:Hide()
            end
        end)
    end
end)

-- =========================================================================
-- Slash
-- =========================================================================
SLASH_AHORACLE1 = "/ahoracle"
SLASH_AHORACLE2 = "/aho"
SlashCmdList["AHORACLE"] = function() A:ToggleFrame() end