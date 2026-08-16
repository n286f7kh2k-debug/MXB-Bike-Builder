from pathlib import Path
import re

path = Path('native-race-day-live/src/MXBRaceDayLive.Profile/ProfileHomeFeature.cs')
text = path.read_text(encoding='utf-8')

if 'private FrameworkElement? _settingsView;' not in text:
    text = text.replace(
        '    private FrameworkElement? _bikeModelView;\n',
        '    private FrameworkElement? _bikeModelView;\n    private FrameworkElement? _settingsView;\n',
        1)

if '        _settingsView = null;\n' not in text:
    text = text.replace(
        '        _bikeModelView = null;\n',
        '        _bikeModelView = null;\n        _settingsView = null;\n',
        1)

old_cards = '''        var garageCard = BuildGarageCard();
        Grid.SetColumn(garageCard, 0);
        garageRow.Children.Add(garageCard);
        stack.Children.Add(garageRow);'''
new_cards = '''        var garageCard = BuildGarageCard();
        Grid.SetColumn(garageCard, 0);
        garageRow.Children.Add(garageCard);
        var settingsCard = BuildSettingsCard();
        Grid.SetColumn(settingsCard, 1);
        garageRow.Children.Add(settingsCard);
        stack.Children.Add(garageRow);'''
if 'var settingsCard = BuildSettingsCard();' not in text:
    if old_cards not in text:
        raise SystemExit('Could not find Garage card block')
    text = text.replace(old_cards, new_cards, 1)

marker = '    private Border BuildGarageCard()\n'
if marker not in text:
    raise SystemExit('Could not find BuildGarageCard marker')

settings_methods = r'''    private Border BuildSettingsCard()
    {
        var card = Card(new Thickness(6, 0, 6, 0));
        card.MinHeight = 176;
        card.Cursor = Cursors.Hand;
        card.ToolTip = "Open Race Day Live settings";
        card.MouseLeftButtonUp += (_, _) => OpenSettings();

        var stack = new StackPanel { Margin = new Thickness(17, 14, 17, 15) };
        stack.Children.Add(Label("SETTINGS", 11, "#F2F7FB", true));
        stack.Children.Add(Label("GAME FILE LINKS", 18, "#079CFF", true, new Thickness(0, 24, 0, 6)));
        stack.Children.Add(Label("Manually link MX Bikes, bikes, rider and gear folders.", 10, "#88A5BA"));
        stack.Children.Add(Label("OPEN SETTINGS  ›", 8.5, "#079CFF", true, new Thickness(0, 25, 0, 0)));
        card.Child = stack;
        return card;
    }

    private void OpenSettings()
    {
        var host = _pageHost;
        var profile = _profileView;
        if (host is null || profile is null) return;

        CancelModelLoad();
        profile.Visibility = Visibility.Collapsed;
        if (_bikeLibraryView is not null) { host.Children.Remove(_bikeLibraryView); _bikeLibraryView = null; }
        if (_bikeModelView is not null) { host.Children.Remove(_bikeModelView); _bikeModelView = null; }
        if (_settingsView is not null) host.Children.Remove(_settingsView);

        var page = new Grid { Background = Brush("#04101B") };
        page.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        page.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        page.Children.Add(BuildPageHeader("‹  BACK TO PROFILE", CloseSettings, "SETTINGS", "Race Day Live configuration and MX Bikes file links."));

        var scroll = new ScrollViewer
        {
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled
        };
        var body = new StackPanel { Margin = new Thickness(32, 26, 32, 40) };
        scroll.Content = body;
        Grid.SetRow(scroll, 1);
        page.Children.Add(scroll);

        body.Children.Add(SectionTitle("GAME FILE LINKS", "Set these manually when auto-detection does not match the user's MX Bikes installation. Saved links take priority in the Garage."));

        var saved = GameFileLinks.Load();
        var fields = new Dictionary<string, TextBox>(StringComparer.OrdinalIgnoreCase);

        void AddPathRow(string key, string title, string help, string value)
        {
            var card = Card(new Thickness(0, 0, 0, 10));
            var grid = new Grid { Margin = new Thickness(18, 14, 18, 14) };
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(190) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            card.Child = grid;

            var left = new StackPanel { VerticalAlignment = VerticalAlignment.Center };
            left.Children.Add(Label(title, 11, "#F2F7FB", true));
            var helper = Label(help, 9, "#688596", false, new Thickness(0, 3, 12, 0));
            helper.TextWrapping = TextWrapping.Wrap;
            left.Children.Add(helper);
            grid.Children.Add(left);

            var editWrap = new Grid { Margin = new Thickness(10, 0, 10, 0) };
            editWrap.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            editWrap.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            var box = new TextBox
            {
                Text = value ?? string.Empty,
                Background = Brush("#04101B"),
                Foreground = Brush("#F2F7FB"),
                BorderBrush = Brush("#155273"),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(10, 7, 10, 7),
                FontSize = 11,
                VerticalContentAlignment = VerticalAlignment.Center
            };
            fields[key] = box;
            editWrap.Children.Add(box);
            var status = Label(GameFileLinks.Exists(box.Text) ? "LINK FOUND" : (string.IsNullOrWhiteSpace(box.Text) ? "NOT SET" : "PATH NOT FOUND"), 8.5,
                GameFileLinks.Exists(box.Text) ? "#2BD672" : "#F4C542", true, new Thickness(2, 5, 0, 0));
            Grid.SetRow(status, 1);
            editWrap.Children.Add(status);
            box.TextChanged += (_, _) =>
            {
                var ok = GameFileLinks.Exists(box.Text);
                status.Text = ok ? "LINK FOUND" : (string.IsNullOrWhiteSpace(box.Text) ? "NOT SET" : "PATH NOT FOUND");
                status.Foreground = Brush(ok ? "#2BD672" : "#F4C542");
            };
            Grid.SetColumn(editWrap, 1);
            grid.Children.Add(editWrap);

            var browse = new Button
            {
                Content = "BROWSE",
                Background = Brush("#0A2235"),
                Foreground = Brush("#F2F7FB"),
                BorderBrush = Brush("#155273"),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(13, 8, 13, 8),
                Cursor = Cursors.Hand,
                VerticalAlignment = VerticalAlignment.Center
            };
            browse.Click += (_, _) =>
            {
                var dialog = new Microsoft.Win32.OpenFolderDialog
                {
                    Title = "Select " + title,
                    Multiselect = false
                };
                if (!string.IsNullOrWhiteSpace(box.Text) && Directory.Exists(box.Text)) dialog.InitialDirectory = box.Text;
                if (dialog.ShowDialog() == true) box.Text = dialog.FolderName;
            };
            Grid.SetColumn(browse, 2);
            grid.Children.Add(browse);
            body.Children.Add(card);
        }

        AddPathRow("game", "MX Bikes Install", "Folder containing mxbikes.exe and stock game content.", saved.GameInstallDirectory);
        AddPathRow("user", "MX Bikes User Data", "Usually Documents\\PiBoSo\\MX Bikes.", saved.UserDataDirectory);
        AddPathRow("mods", "Mods Folder", "Root MX Bikes mods folder.", saved.ModsDirectory);
        AddPathRow("bikes", "Bikes Folder", "Folder containing installed bike folders and PKZ files.", saved.BikesDirectory);
        AddPathRow("rider", "Rider Folder", "Root rider content folder.", saved.RiderDirectory);
        AddPathRow("helmets", "Helmets Folder", "Installed helmet models and paints.", saved.HelmetsDirectory);
        AddPathRow("boots", "Boots Folder", "Installed boot models and paints.", saved.BootsDirectory);
        AddPathRow("paints", "Paints Folder", "Optional custom paint/library location.", saved.PaintsDirectory);

        var actions = new WrapPanel { Margin = new Thickness(0, 12, 0, 0) };
        var feedback = Label("", 10, "#88A5BA", true, new Thickness(14, 9, 0, 0));

        GameFileLinkSettings ReadFields() => new(
            fields["game"].Text,
            fields["user"].Text,
            fields["mods"].Text,
            fields["bikes"].Text,
            fields["rider"].Text,
            fields["helmets"].Text,
            fields["boots"].Text,
            fields["paints"].Text);

        void WriteFields(GameFileLinkSettings s)
        {
            fields["game"].Text = s.GameInstallDirectory;
            fields["user"].Text = s.UserDataDirectory;
            fields["mods"].Text = s.ModsDirectory;
            fields["bikes"].Text = s.BikesDirectory;
            fields["rider"].Text = s.RiderDirectory;
            fields["helmets"].Text = s.HelmetsDirectory;
            fields["boots"].Text = s.BootsDirectory;
            fields["paints"].Text = s.PaintsDirectory;
        }

        Button ActionButton(string text, string color = "#0A2235") => new()
        {
            Content = text,
            Background = Brush(color),
            Foreground = Brush("#F2F7FB"),
            BorderBrush = Brush("#155273"),
            BorderThickness = new Thickness(1),
            Padding = new Thickness(16, 9, 16, 9),
            Margin = new Thickness(0, 0, 9, 9),
            Cursor = Cursors.Hand
        };

        var auto = ActionButton("AUTO-FILL FROM MX BIKES");
        auto.Click += async (_, _) =>
        {
            if (_context is null) return;
            try
            {
                feedback.Text = "DETECTING MX BIKES…";
                var env = await _context.MXBikes.DetectEnvironmentAsync();
                WriteFields(GameFileLinks.AutoFill(ReadFields(), env));
                feedback.Text = "AUTO-FILL COMPLETE";
                feedback.Foreground = Brush("#2BD672");
            }
            catch (Exception ex)
            {
                feedback.Text = "AUTO-FILL FAILED · " + ex.Message;
                feedback.Foreground = Brush("#FF5964");
            }
        };
        actions.Children.Add(auto);

        var clear = ActionButton("CLEAR LINKS");
        clear.Click += (_, _) =>
        {
            WriteFields(new());
            feedback.Text = "LINKS CLEARED · SAVE TO APPLY";
            feedback.Foreground = Brush("#F4C542");
        };
        actions.Children.Add(clear);

        var save = ActionButton("SAVE & RESCAN", "#0A4F78");
        save.Click += async (_, _) =>
        {
            try
            {
                feedback.Text = "SAVING…";
                await GameFileLinks.SaveAsync(ReadFields());
                var count = GameFileLinks.ScanManualBikes().Count;
                feedback.Text = $"SAVED · {count} MANUALLY LINKED BIKE ENTRIES FOUND";
                feedback.Foreground = Brush("#2BD672");
            }
            catch (Exception ex)
            {
                feedback.Text = "SAVE FAILED · " + ex.Message;
                feedback.Foreground = Brush("#FF5964");
            }
        };
        actions.Children.Add(save);
        actions.Children.Add(feedback);
        body.Children.Add(actions);

        var note = Card(new Thickness(0, 18, 0, 0));
        var noteStack = new StackPanel { Margin = new Thickness(18) };
        noteStack.Children.Add(Label("MANUAL LINKS OVERRIDE AUTO-DETECTION", 10, "#079CFF", true));
        var noteBody = Label("The Garage uses the manually linked Bikes folder first for matching bike IDs. Auto-detected game content is still kept as a fallback, so users can mix stock and mod locations safely.", 10.5, "#88A5BA", false, new Thickness(0, 6, 0, 0));
        noteBody.TextWrapping = TextWrapping.Wrap;
        noteStack.Children.Add(noteBody);
        note.Child = noteStack;
        body.Children.Add(note);

        _settingsView = page;
        host.Children.Add(page);
    }

    private void CloseSettings()
    {
        var host = _pageHost;
        var profile = _profileView;
        if (host is null || profile is null) return;
        if (_settingsView is not null)
        {
            host.Children.Remove(_settingsView);
            _settingsView = null;
        }
        profile.Visibility = Visibility.Visible;
    }

'''

if 'private Border BuildSettingsCard()' not in text:
    text = text.replace(marker, settings_methods + marker, 1)

old_scan = '''            var current = await context.MXBikes.ReadActiveSelectionAsync();
            var content = await context.MXBikes.ScanInstalledContentAsync();
            var bikes = content
                .Where(x => string.Equals(x.ContentType, "BIKE", StringComparison.OrdinalIgnoreCase))
                .OrderBy(x => Friendly(x.DisplayName), StringComparer.OrdinalIgnoreCase)
                .ToArray();'''
new_scan = '''            var current = await context.MXBikes.ReadActiveSelectionAsync();
            var content = await context.MXBikes.ScanInstalledContentAsync();
            var bikeMap = content
                .Where(x => string.Equals(x.ContentType, "BIKE", StringComparison.OrdinalIgnoreCase))
                .GroupBy(x => x.Id, StringComparer.OrdinalIgnoreCase)
                .ToDictionary(g => g.Key, g => g.First(), StringComparer.OrdinalIgnoreCase);
            foreach (var manual in GameFileLinks.ScanManualBikes())
                bikeMap[manual.Id] = manual; // manual Settings link wins
            var bikes = bikeMap.Values
                .OrderBy(x => Friendly(x.DisplayName), StringComparer.OrdinalIgnoreCase)
                .ToArray();'''
if 'foreach (var manual in GameFileLinks.ScanManualBikes())' not in text:
    if old_scan not in text:
        raise SystemExit('Could not find Garage scan block')
    text = text.replace(old_scan, new_scan, 1)

path.write_text(text, encoding='utf-8')

project = Path('native-race-day-live/src/MXBRaceDayLive.Profile/MXBRaceDayLive.Profile.csproj')
csproj = project.read_text(encoding='utf-8')
csproj = re.sub(r'<Version>[^<]+</Version>', '<Version>1.0.11</Version>', csproj, count=1)
project.write_text(csproj, encoding='utf-8')
