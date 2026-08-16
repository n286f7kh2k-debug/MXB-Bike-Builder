from pathlib import Path

path = Path('native-race-day-live/src/MXBRaceDayLive.Profile/ProfileHomeFeature.cs')
s = path.read_text(encoding='utf-8')
start = s.index('    private FrameworkElement Build(RiderProfile rider)')
end = s.index('    private Border BuildSettingsCard()', start)

replacement = r'''    private FrameworkElement Build(RiderProfile rider)
    {
        _pageHost = new Grid { Background = PageBackground(), ClipToBounds = true };
        AddRaceNightBackdrop(_pageHost);

        _profileView = new ScrollViewer
        {
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
            Background = Brushes.Transparent
        };

        var dashboard = new Grid { Margin = new Thickness(14, 12, 18, 22) };
        dashboard.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(154) });
        dashboard.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        _profileView.Content = dashboard;
        _pageHost.Children.Add(_profileView);

        var rail = BuildDashboardRail(rider);
        Grid.SetColumn(rail, 0);
        dashboard.Children.Add(rail);

        var content = new StackPanel { Margin = new Thickness(14, 0, 0, 0) };
        Grid.SetColumn(content, 1);
        dashboard.Children.Add(content);

        var pageHeading = new Grid { Margin = new Thickness(2, 0, 0, 10) };
        pageHeading.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        pageHeading.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var headingStack = new StackPanel();
        var heading = Label("MY PROFILE", 24, "#F7FBFF", true);
        heading.FontFamily = new FontFamily("Segoe UI Black");
        heading.FontStyle = FontStyles.Italic;
        headingStack.Children.Add(heading);
        headingStack.Children.Add(Label("RIDER HUB  /  MX BIKES LIVE PROFILE", 8.5, "#5D8EAB", true, new Thickness(1, -1, 0, 0)));
        pageHeading.Children.Add(headingStack);
        var liveBadge = new Border
        {
            Background = Brush("#071D2C"), BorderBrush = Brush("#0AAEFF"), BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(5), Padding = new Thickness(10, 6, 10, 6), VerticalAlignment = VerticalAlignment.Center
        };
        var liveText = Label("●  MX BIKES LINKED", 8.5, "#2BD672", true);
        liveBadge.Child = liveText;
        Grid.SetColumn(liveBadge, 1);
        pageHeading.Children.Add(liveBadge);
        content.Children.Add(pageHeading);

        var top = new Grid { Margin = new Thickness(0, 0, 0, 10) };
        top.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1.62, GridUnitType.Star) });
        top.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

        var hero = BuildDashboardProfileCard(rider);
        hero.Margin = new Thickness(0, 0, 6, 0);
        Grid.SetColumn(hero, 0);
        top.Children.Add(hero);

        var statPanel = BuildDashboardStats(rider);
        statPanel.Margin = new Thickness(6, 0, 0, 0);
        Grid.SetColumn(statPanel, 1);
        top.Children.Add(statPanel);
        content.Children.Add(top);

        var lower = new Grid();
        lower.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(0.92, GridUnitType.Star) });
        lower.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1.75, GridUnitType.Star) });

        var tools = new StackPanel { Margin = new Thickness(0, 0, 6, 0) };
        var garage = BuildGarageCard();
        garage.Margin = new Thickness(0, 0, 0, 10);
        tools.Children.Add(garage);
        var settings = BuildSettingsCard();
        settings.Margin = new Thickness(0);
        tools.Children.Add(settings);
        Grid.SetColumn(tools, 0);
        lower.Children.Add(tools);

        var raceArea = new StackPanel { Margin = new Thickness(6, 0, 0, 0) };
        var races = BuildDashboardRacesCard();
        races.Margin = new Thickness(0, 0, 0, 10);
        raceArea.Children.Add(races);

        var snapshot = new Grid();
        snapshot.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        snapshot.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        snapshot.Children.Add(SnapshotCard("NEXT RACE", "NO RACE REGISTERED", "Your next race will appear here.", 0));
        snapshot.Children.Add(SnapshotCard("LATEST RESULT", "NO RESULTS YET", "Completed results will appear here.", 1));
        raceArea.Children.Add(snapshot);
        Grid.SetColumn(raceArea, 1);
        lower.Children.Add(raceArea);
        content.Children.Add(lower);

        return _pageHost;
    }

    private FrameworkElement BuildDashboardRail(RiderProfile rider)
    {
        var rail = new Border
        {
            Background = FeatureCardBackground("#071827", "#030B12"),
            BorderBrush = Brush("#0B5279"), BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(7),
            Effect = Glow("#003A61", 18, 0.24)
        };
        var root = new Grid { Margin = new Thickness(10, 13, 10, 12) };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        rail.Child = root;

        var logo = new StackPanel { Margin = new Thickness(5, 0, 0, 18) };
        var mxb = Label("MXB", 28, "#FFFFFF", true);
        mxb.FontFamily = new FontFamily("Segoe UI Black"); mxb.FontStyle = FontStyles.Italic;
        logo.Children.Add(mxb);
        var rdl = Label("RACE DAY LIVE", 9, "#0AB9FF", true, new Thickness(1, -3, 0, 0));
        rdl.FontStyle = FontStyles.Italic; logo.Children.Add(rdl);
        root.Children.Add(logo);

        var nav = new StackPanel();
        nav.Children.Add(DashboardNavButton("◈", "MY PROFILE", true, null));
        nav.Children.Add(DashboardNavButton("▣", "GARAGE", false, async () => await OpenBikeLibraryAsync()));
        nav.Children.Add(DashboardNavButton("⚙", "SETTINGS", false, () => OpenSettings()));
        Grid.SetRow(nav, 1);
        root.Children.Add(nav);

        var riderTag = new Border
        {
            Background = Brush("#06131E"), BorderBrush = Brush("#123D57"), BorderThickness = new Thickness(1, 1, 1, 0),
            Padding = new Thickness(7, 9, 7, 3)
        };
        var riderStack = new StackPanel();
        riderStack.Children.Add(Label("SIGNED IN AS", 7.5, "#557C92", true));
        var riderName = Label(rider.DisplayName.ToUpperInvariant(), 9.5, "#F5FAFD", true, new Thickness(0, 3, 0, 0));
        riderName.TextTrimming = TextTrimming.CharacterEllipsis;
        riderStack.Children.Add(riderName);
        riderStack.Children.Add(Label("#" + rider.RacingNumber, 15, "#0AB9FF", true, new Thickness(0, 1, 0, 0)));
        riderTag.Child = riderStack;
        Grid.SetRow(riderTag, 2);
        root.Children.Add(riderTag);
        return rail;
    }

    private FrameworkElement DashboardNavButton(string icon, string text, bool active, Action? action)
    {
        var border = new Border
        {
            Background = Brush(active ? "#073C64" : "#04121D"),
            BorderBrush = Brush(active ? "#0AAEFF" : "#12364B"), BorderThickness = new Thickness(active ? 2 : 1, 1, 1, 1),
            CornerRadius = new CornerRadius(4), Margin = new Thickness(0, 0, 0, 7), Padding = new Thickness(8, 8, 6, 8),
            Cursor = action is null ? Cursors.Arrow : Cursors.Hand
        };
        var row = new StackPanel { Orientation = Orientation.Horizontal };
        row.Children.Add(Label(icon, 11, active ? "#6DD5FF" : "#6F8FA2", true, new Thickness(0, 0, 7, 0)));
        var label = Label(text, 8.5, active ? "#FFFFFF" : "#A9BBC7", true);
        label.FontStyle = FontStyles.Italic;
        row.Children.Add(label);
        border.Child = row;
        if (action is not null) border.MouseLeftButtonUp += (_, _) => action();
        return border;
    }

    private Border BuildDashboardProfileCard(RiderProfile rider)
    {
        var card = new Border
        {
            Background = Brush("#04101B"), BorderBrush = Brush("#0AAEFF"), BorderThickness = new Thickness(1.2),
            CornerRadius = new CornerRadius(7), ClipToBounds = true, MinHeight = 315, Effect = Glow("#0078C9", 20, 0.22)
        };
        var grid = new Grid();
        grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(196) });
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        card.Child = grid;

        var hero = new Grid { Background = HeroBackground(), ClipToBounds = true };
        var bannerBrush = TryImageBrush(rider.BannerPath);
        if (bannerBrush is not null)
        {
            hero.Children.Add(new Rectangle { Fill = bannerBrush, Opacity = 0.62, IsHitTestVisible = false });
            hero.Children.Add(new Rectangle
            {
                Fill = new LinearGradientBrush(Color("#D9000710"), Color("#55000B14"), 0), IsHitTestVisible = false
            });
        }
        hero.Children.Add(new Polygon
        {
            Points = new PointCollection(new[] { new Point(365,-30), new Point(480,-30), new Point(305,220), new Point(198,220) }),
            Fill = Brush("#007FD0"), Opacity = 0.34, IsHitTestVisible = false
        });
        hero.Children.Add(new Polygon
        {
            Points = new PointCollection(new[] { new Point(455,-30), new Point(515,-30), new Point(342,220), new Point(287,220) }),
            Fill = Brush("#16C6FF"), Opacity = 0.22, IsHitTestVisible = false
        });
        hero.Children.Add(new Border
        {
            Height = 4, Background = Brush("#0AB9FF"), VerticalAlignment = VerticalAlignment.Bottom,
            Effect = Glow("#00A8FF", 16, 0.75)
        });

        var avatar = new Grid { Width = 94, Height = 94, HorizontalAlignment = HorizontalAlignment.Left, VerticalAlignment = VerticalAlignment.Bottom, Margin = new Thickness(22,0,0,19) };
        var avatarFill = TryImageBrush(rider.AvatarPath) ?? new LinearGradientBrush(Color("#0D3551"), Color("#06131F"), 45);
        avatar.Children.Add(new Ellipse { Fill = avatarFill, Stroke = Brush("#E8F7FF"), StrokeThickness = 3, Effect = Glow("#00A8FF", 18, 0.50) });
        if (TryImageBrush(rider.AvatarPath) is null)
            avatar.Children.Add(new TextBlock { Text = Initials(rider.DisplayName), Foreground = Brushes.White, FontFamily = new FontFamily("Segoe UI Black"), FontSize = 26, HorizontalAlignment = HorizontalAlignment.Center, VerticalAlignment = VerticalAlignment.Center });
        hero.Children.Add(avatar);

        var identity = new StackPanel { HorizontalAlignment = HorizontalAlignment.Left, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(135, 18, 15, 0) };
        var name = Label(rider.DisplayName.ToUpperInvariant(), 27, "#FFFFFF", true); name.FontFamily = new FontFamily("Segoe UI Black"); name.FontStyle = FontStyles.Italic;
        identity.Children.Add(name);
        var number = Label("#" + rider.RacingNumber, 36, "#16C9FF", true, new Thickness(0,-4,0,0)); number.FontFamily = new FontFamily("Segoe UI Black"); number.FontStyle = FontStyles.Italic; number.Effect = Glow("#009DFF", 16, .5);
        identity.Children.Add(number);
        identity.Children.Add(Label(string.Join("  •  ", new[] { rider.Team, rider.Region }.Where(x => !string.IsNullOrWhiteSpace(x))), 9.5, "#A9C1CF", true, new Thickness(1,2,0,0)));
        hero.Children.Add(identity);

        var rank = new Border
        {
            Background = Brush("#C805111B"), BorderBrush = Brush("#72572A"), BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(4),
            Padding = new Thickness(11,8,11,8), HorizontalAlignment = HorizontalAlignment.Right, VerticalAlignment = VerticalAlignment.Bottom, Margin = new Thickness(0,0,17,19)
        };
        var rankStack = new StackPanel();
        rankStack.Children.Add(Label("RANK", 7.5, "#A98D5A", true));
        rankStack.Children.Add(Label(rider.OverallRank > 0 ? "#" + rider.OverallRank : "UNRANKED", 18, "#F4C542", true));
        rank.Child = rankStack; hero.Children.Add(rank);
        grid.Children.Add(hero);

        var info = new Grid { Margin = new Thickness(18, 13, 18, 14) };
        info.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        info.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var bio = Label(string.IsNullOrWhiteSpace(rider.Bio) ? "Your MX Bikes racing profile lives here." : rider.Bio, 10.5, "#A9BBC7");
        bio.TextWrapping = TextWrapping.Wrap; bio.MaxWidth = 650; info.Children.Add(bio);
        var status = Label("●  LIVE PROFILE", 8, "#2BD672", true, new Thickness(12,0,0,0));
        Grid.SetColumn(status, 1); info.Children.Add(status);
        Grid.SetRow(info, 1); grid.Children.Add(info);
        return card;
    }

    private Border BuildDashboardStats(RiderProfile rider)
    {
        var panel = new Border
        {
            Background = FeatureCardBackground("#071C2B", "#030C14"), BorderBrush = Brush("#0B5279"), BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(7), MinHeight = 315
        };
        var root = new Grid { Margin = new Thickness(12) };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        panel.Child = root;
        var title = Label("RIDER STATUS", 12.5, "#FFFFFF", true, new Thickness(2,0,0,9)); title.FontFamily = new FontFamily("Segoe UI Black"); title.FontStyle = FontStyles.Italic; root.Children.Add(title);
        var grid = new Grid();
        grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        Grid.SetRow(grid,1); root.Children.Add(grid);
        AddDashboardStat(grid,0,0,"SKILL",rider.SkillClass.ToUpperInvariant(),rider.SkillRating + " MMR","#F4C542");
        AddDashboardStat(grid,1,0,"ETIQUETTE",rider.EtiquetteGrade,rider.EtiquetteScore.ToString(),"#2BD672");
        AddDashboardStat(grid,0,1,"CAREER STARTS","0","RACES","#F7FBFF");
        AddDashboardStat(grid,1,1,"WINS / PODIUMS","0 / 0","CAREER","#F7FBFF");
        return panel;
    }

    private void AddDashboardStat(Grid grid, int column, int row, string title, string value, string sub, string valueColor)
    {
        var card = new Border
        {
            Background = Brush("#06131E"), BorderBrush = Brush("#123B54"), BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(5),
            Margin = new Thickness(column == 0 ? 0 : 5, row == 0 ? 0 : 5, column == 0 ? 5 : 0, row == 0 ? 5 : 0), Padding = new Thickness(11,10,8,8)
        };
        var stack = new StackPanel();
        stack.Children.Add(Label(title, 7.5, "#63899F", true));
        var val = Label(value, 16, valueColor, true, new Thickness(0,5,0,0)); val.FontFamily = new FontFamily("Segoe UI Black"); val.FontStyle = FontStyles.Italic; stack.Children.Add(val);
        stack.Children.Add(Label(sub, 8, "#8BA5B5", true, new Thickness(0,2,0,0)));
        card.Child = stack; Grid.SetColumn(card,column); Grid.SetRow(card,row); grid.Children.Add(card);
    }

    private Border BuildDashboardRacesCard()
    {
        var card = new Border
        {
            Background = FeatureCardBackground("#071C2B", "#030C14"), BorderBrush = Brush("#0B5279"), BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(7), MinHeight = 362, ClipToBounds = true
        };
        var root = new Grid();
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        card.Child = root;
        var header = new Grid { Background = Brush("#071827"), Margin = new Thickness(0), Height = 45 };
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var title = Label("MY RACES", 13, "#FFFFFF", true, new Thickness(14,13,0,0)); title.FontFamily = new FontFamily("Segoe UI Black"); title.FontStyle = FontStyles.Italic; header.Children.Add(title);
        var tabs = Label("UPCOMING   |   RECENT   |   RESULTS", 7.5, "#6CA4C3", true, new Thickness(0,15,14,0)); Grid.SetColumn(tabs,1); header.Children.Add(tabs);
        root.Children.Add(header);
        var body = new Grid { Margin = new Thickness(14) };
        var panel = new Border { Background = Brush("#04111B"), BorderBrush = Brush("#123B54"), BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(5), Padding = new Thickness(16) };
        var stack = new StackPanel { VerticalAlignment = VerticalAlignment.Center };
        var empty = Label("NO REGISTERED RACES YET", 15, "#F7FBFF", true); empty.FontFamily = new FontFamily("Segoe UI Black"); empty.FontStyle = FontStyles.Italic; stack.Children.Add(empty);
        stack.Children.Add(Label("Registered races will appear here with the same compact race-card treatment.", 9.5, "#7899AE", false, new Thickness(0,5,0,0)));
        panel.Child = stack; body.Children.Add(panel); Grid.SetRow(body,1); root.Children.Add(body);
        return card;
    }

    private static ImageBrush? TryImageBrush(string? path)
    {
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path)) return null;
        try
        {
            var image = new System.Windows.Media.Imaging.BitmapImage();
            image.BeginInit();
            image.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad;
            image.UriSource = new Uri(path, UriKind.Absolute);
            image.EndInit();
            image.Freeze();
            return new ImageBrush(image) { Stretch = Stretch.UniformToFill, AlignmentX = AlignmentX.Center, AlignmentY = AlignmentY.Center };
        }
        catch { return null; }
    }

'''

s = s[:start] + replacement + s[end:]
path.write_text(s, encoding='utf-8')

proj = Path('native-race-day-live/src/MXBRaceDayLive.Profile/MXBRaceDayLive.Profile.csproj')
p = proj.read_text(encoding='utf-8')
p = p.replace('<Version>1.0.14</Version>', '<Version>1.0.15</Version>').replace('<Version>1.0.13</Version>', '<Version>1.0.15</Version>')
proj.write_text(p, encoding='utf-8')
