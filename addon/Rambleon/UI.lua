-- Rambleon: the adventure log panel. Function first; parchment feel with built-in textures only.
local ADDON, ns = ...
ns.UI = {}
local UI = ns.UI

local WIDTH, HEIGHT = 380, 578

-- The rows under "Current Session": a key of Journal.Stats(), its label, and how to show it (default: as it is).
local STAT_ROWS = {
  { key = "played", label = "Time", format = function(v) return ns.FormatDuration(v) end },
  { key = "area", label = "Current Area" },
  { key = "level", label = "Level" },
  { key = "questsCompleted", label = "Quests Completed" },
  { key = "places", label = "Places Visited" },
  { key = "kills", label = "Enemies Slain" },
  { key = "loot", label = "Loot Worth Keeping" },
  { key = "deaths", label = "Deaths" },
  { key = "people", label = "People Met" },
}
local RECENT = 10
local TITLE_FONT = "Fonts\\MORPHEUS.TTF"
local BODY_FONT = "Fonts\\FRIZQT__.TTF"
local INK = { 0.24, 0.16, 0.08 }         -- dark brown text
local INK_SOFT = { 0.42, 0.30, 0.16 }
local GOLD = { 0.62, 0.42, 0.12 }

local panel

local function setFont(fs, path, size, flags)
  local ok = pcall(fs.SetFont, fs, path, size, flags or "")
  if not ok then fs:SetFontObject(GameFontNormal) end
end

local function label(parent, text, size, color, font)
  local fs = parent:CreateFontString(nil, "OVERLAY", "GameFontNormal")
  setFont(fs, font or BODY_FONT, size or 12)
  fs:SetTextColor(color[1], color[2], color[3])
  fs:SetJustifyH("LEFT")
  fs:SetText(text or "")
  return fs
end

local function button(parent, text, width)
  local b = CreateFrame("Button", nil, parent, "UIPanelButtonTemplate")
  b:SetSize(width or 110, 24)
  b:SetText(text)
  return b
end

local function build()
  local template = BackdropTemplateMixin and "BackdropTemplate" or nil
  panel = CreateFrame("Frame", "RambleonPanel", UIParent, template)
  panel:SetSize(WIDTH, HEIGHT)
  panel:SetPoint("CENTER", UIParent, "CENTER", 0, 40)
  panel:SetFrameStrata("MEDIUM")
  panel:SetMovable(true)
  panel:EnableMouse(true)
  panel:SetClampedToScreen(true)
  panel:RegisterForDrag("LeftButton")
  panel:SetScript("OnDragStart", panel.StartMoving)
  panel:SetScript("OnDragStop", panel.StopMovingOrSizing)
  if panel.SetBackdrop then
    panel:SetBackdrop({
      bgFile = "Interface\\Buttons\\WHITE8X8",
      edgeFile = "Interface\\DialogFrame\\UI-DialogBox-Border",
      tile = false, edgeSize = 32,
      insets = { left = 10, right = 10, top = 10, bottom = 10 },
    })
    panel:SetBackdropColor(0.90, 0.82, 0.64, 0.97)     -- parchment
    panel:SetBackdropBorderColor(0.75, 0.60, 0.35, 1)
  end
  -- Optional parchment atlas; harmless if the atlas does not exist on this client.
  local parchment = panel:CreateTexture(nil, "BACKGROUND", nil, 1)
  parchment:SetPoint("TOPLEFT", 12, -12)
  parchment:SetPoint("BOTTOMRIGHT", -12, 12)
  local ok = pcall(parchment.SetAtlas, parchment, "QuestBG-Parchment", true)
  if ok then parchment:SetAlpha(0.35) else parchment:Hide() end

  -- Escape closes
  tinsert(UISpecialFrames, "RambleonPanel")

  local close = CreateFrame("Button", nil, panel, "UIPanelCloseButton")
  close:SetPoint("TOPRIGHT", -4, -4)

  panel.title = label(panel, "RAMBLEON", 22, GOLD, TITLE_FONT)
  panel.title:SetPoint("TOP", 0, -22)
  panel.title:SetJustifyH("CENTER")
  panel.subtitle = label(panel, "ADVENTURE LOG", 11, INK_SOFT)
  panel.subtitle:SetPoint("TOP", panel.title, "BOTTOM", 0, -2)
  panel.subtitle:SetJustifyH("CENTER")

  local y = -74
  panel.sectionSession = label(panel, "Current Session", 14, GOLD, TITLE_FONT)
  panel.sectionSession:SetPoint("TOPLEFT", 26, y)
  y = y - 22

  local function row(text)
    local k = label(panel, text, 12, INK_SOFT)
    k:SetPoint("TOPLEFT", 30, y)
    local v = label(panel, "—", 12, INK)
    v:SetPoint("TOPLEFT", 160, y)
    v:SetWidth(WIDTH - 190)
    v:SetWordWrap(false)
    y = y - 17
    return v
  end
  panel.stats = {}
  for _, r in ipairs(STAT_ROWS) do
    panel.stats[r.key] = row(r.label)
  end
  -- The one setting worth a click: automatic pictures, on or off (same as /ramble shots on|off).
  local picturesTop = y
  panel.pictures = row("Pictures")
  panel.picturesToggle = CreateFrame("Button", nil, panel)
  panel.picturesToggle:SetPoint("TOPLEFT", 26, picturesTop + 2)
  panel.picturesToggle:SetSize(WIDTH - 52, 17)
  panel.picturesToggle:SetScript("OnClick", function()
    ns.SetAutoShots(not ns.AutoShotsEnabled())
    UI.Refresh()
  end)

  y = y - 10
  panel.sectionJourney = label(panel, "Recent Journey", 14, GOLD, TITLE_FONT)
  panel.sectionJourney:SetPoint("TOPLEFT", 26, y)
  y = y - 22

  panel.lines = {}
  for i = 1, RECENT do
    local t = label(panel, "", 11, INK_SOFT)
    t:SetPoint("TOPLEFT", 30, y)
    t:SetWidth(58)
    local d = label(panel, "", 11, INK)
    d:SetPoint("TOPLEFT", 90, y)
    d:SetWidth(WIDTH - 120)
    d:SetWordWrap(false)
    panel.lines[i] = { time = t, text = d }
    y = y - 15
  end

  panel.banner = label(panel, "", 11, GOLD)
  panel.banner:SetPoint("BOTTOM", 0, 82)      -- clear of the footer, which wraps to two lines
  panel.banner:SetJustifyH("CENTER")
  panel.banner:SetWidth(WIDTH - 60)

  panel.footer = label(panel, "Your log saves itself when you log out.", 10, INK_SOFT)
  panel.footer:SetPoint("BOTTOM", 0, 50); panel.footer:SetJustifyH("CENTER"); panel.footer:SetWidth(WIDTH - 50)

  local mark = button(panel, "MARK MOMENT", 167)
  mark:SetPoint("BOTTOMLEFT", 20, 18)
  mark:SetScript("OnClick", function() ns.MarkMoment() end)
  local note = button(panel, "ADD NOTE", 167)
  note:SetPoint("LEFT", mark, "RIGHT", 6, 0)
  note:SetScript("OnClick", UI.PromptNote)

  local acc = 0
  panel:SetScript("OnUpdate", function(self, elapsed)
    acc = acc + elapsed
    if acc >= 1 or ns.dirty then
      acc = 0
      UI.Refresh()
    end
  end)
  panel:SetScript("OnShow", UI.Refresh)
  panel:Hide()
  return panel
end

function UI.Get()
  return panel or build()
end

function UI.Refresh()
  if not panel or not panel:IsShown() then return end
  ns.dirty = false
  panel.title:SetText(string.upper(ns.DisplayName()))
  local st = ns.Journal.Stats()
  if st then
    for _, r in ipairs(STAT_ROWS) do
      local v = st[r.key]
      panel.stats[r.key]:SetText(r.format and r.format(v) or tostring(v))
    end
  end
  panel.pictures:SetText(ns.AutoShotsEnabled() and "automatic  (click to turn off)" or "off  (click to turn on)")
  local recent = ns.Journal.RecentEvents(RECENT)
  for i = 1, RECENT do
    local ev = recent[i]
    if ev then
      panel.lines[i].time:SetText(ns.FormatClock(ev.t))
      panel.lines[i].text:SetText(ns.Journal.DescribeEvent(ev))
    else
      panel.lines[i].time:SetText("")
      panel.lines[i].text:SetText("")
    end
  end
  if ns.session and ns.session.state == "ended" then
    panel.banner:SetText("Saved. Type /reload to write it to disk.")
  elseif UI.bannerUntil and GetTime() < UI.bannerUntil then
    -- keep transient banner
  else
    panel.banner:SetText("")
  end
end

function UI.Toggle()
  local p = UI.Get()
  if p:IsShown() then p:Hide() return end
  p:Show()
  UI.MaybeWelcome()
end

-- Once, the first time a new player opens the log: what this is, and that there is nothing to press.
function UI.MaybeWelcome()
  if not ns.IsFirstRun() then return end
  ns.SetSetting("welcomed", true)
  StaticPopup_Show("RAMBLEON_WELCOME")
end

-- Our own frames stay out of the pictures. Returns a function that shows them again.
function UI.HideForScreenshot()
  local hidden = {}
  if panel and panel:IsShown() then panel:Hide(); table.insert(hidden, panel) end
  return function() for _, f in ipairs(hidden) do f:Show() end end
end

function UI.Flash(text, seconds)
  local p = UI.Get()
  p.banner:SetText(text)
  UI.bannerUntil = GetTime() + (seconds or 3)
  ns.dirty = true
end

function UI.MomentRemembered()
  ns.Print("Moment remembered.")
  UI.Flash("Moment remembered.", 3)
  if PlaySound and SOUNDKIT and SOUNDKIT.IG_QUEST_LOG_OPEN then
    pcall(PlaySound, SOUNDKIT.IG_QUEST_LOG_OPEN)
  end
end

-- Popups -----------------------------------------------------------------------

StaticPopupDialogs["RAMBLEON_NOTE"] = {
  text = "What just happened?",
  button1 = "SAVE NOTE",
  button2 = CANCEL or "Cancel",
  hasEditBox = true,
  editBoxWidth = 300,
  maxLetters = ns.NOTE_MAX,
  OnAccept = function(self)
    local text = self.editBox and self.editBox:GetText() or ""
    UI.SaveNote(text)
  end,
  EditBoxOnEnterPressed = function(self)
    local parent = self:GetParent()
    UI.SaveNote(self:GetText())
    parent:Hide()
  end,
  EditBoxOnEscapePressed = function(self) self:GetParent():Hide() end,
  OnShow = function(self) if self.editBox then self.editBox:SetText(""); self.editBox:SetFocus() end end,
  timeout = 0, whileDead = true, hideOnEscape = true, preferredIndex = 3,
}

StaticPopupDialogs["RAMBLEON_WELCOME"] = {
  text = "Rambleon quietly remembers your adventure: where you went, what you did, who you met.\n\n"
    .. "There is nothing to press. Play, then log out; the companion on your Mac keeps the record.\n\n"
    .. "MARK MOMENT keeps a moment, with a picture. ADD NOTE keeps your own words, which matter most.",
  button1 = "BEGIN",
  timeout = 0, whileDead = true, hideOnEscape = true, preferredIndex = 3,
}

StaticPopupDialogs["RAMBLEON_END"] = {
  text = "Save your log to disk now?\n\nThis reloads the UI, which is when WoW writes AddOn data. Logging out does the same thing, so this is optional.",
  button1 = "SAVE & RELOAD",
  button2 = CANCEL or "Cancel",
  OnAccept = function() UI.EndChapterAndReload() end,
  timeout = 0, whileDead = true, hideOnEscape = true, preferredIndex = 3,
}

function UI.SaveNote(text)
  if ns.AddNote(text) then ns.Print("Noted."); UI.Flash("Noted.", 3) end
end

function UI.PromptNote()
  StaticPopup_Show("RAMBLEON_NOTE")
end

function UI.PromptEndChapter()
  if not ns.session or ns.session.state ~= "active" then
    ns.Print("Nothing new to save. Type /reload to write what is already recorded.")
    return
  end
  StaticPopup_Show("RAMBLEON_END")
end

function UI.EndChapterAndReload()
  local s = ns.EndSession("save")
  if not s then return end
  ns.Print(string.format("Saving %s of adventure...", ns.FormatDuration(s.playedSeconds or 0)))
  ns.dirty = true
  -- This runs from the popup button click (a hardware event). If Forever protects Reload entirely,
  -- the pcall fails or nothing happens, and we fall back to asking for /reload.
  local ok = pcall(function()
    if C_UI and C_UI.Reload then C_UI.Reload() else ReloadUI() end
  end)
  if C_Timer and C_Timer.After then
    C_Timer.After(1, function()
      ns.Print("The UI did not reload on its own. Type /reload to write the log to disk.")
      UI.Flash("Type /reload to save.", 30)
    end)
  end
  if not ok then ns.Warn("reload blocked") end
end
