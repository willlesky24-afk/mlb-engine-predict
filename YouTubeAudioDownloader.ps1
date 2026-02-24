# YouTube Audio Downloader - Standalone Desktop App
# Powered by PowerShell + WPF + yt-dlp

Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Drawing, System.Windows.Forms

$AppDir = $PSScriptRoot
$BinDir = Join-Path $AppDir "bin"
if (!(Test-Path $BinDir)) { New-Item -ItemType Directory -Path $BinDir | Out-Null }

$YtDlpPath = Join-Path $BinDir "yt-dlp.exe"
$FfmpegPath = Join-Path $BinDir "ffmpeg.exe"

# --- UI Definition (XAML) ---
$xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="YouTube Audio Downloader" Height="500" Width="650"
        Background="#0F0F0F" WindowStartupLocation="CenterScreen" ResizeMode="CanMinimize"
        FontFamily="Segoe UI">
    <Window.Resources>
        <Style x:Key="ModernButton" TargetType="Button">
            <Setter Property="Background" Value="#1DB954"/>
            <Setter Property="Foreground" Value="White"/>
            <Setter Property="BorderThickness" Value="0"/>
            <Setter Property="Padding" Value="15,10"/>
            <Setter Property="FontWeight" Value="SemiBold"/>
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="Button">
                        <Border Background="{TemplateBinding Background}" CornerRadius="8">
                            <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
                        </Border>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
            <Style.Triggers>
                <Trigger Property="IsMouseOver" Value="True">
                    <Setter Property="Background" Value="#1ED760"/>
                </Trigger>
                <Trigger Property="IsEnabled" Value="False">
                    <Setter Property="Background" Value="#333333"/>
                    <Setter Property="Foreground" Value="#888888"/>
                </Trigger>
            </Style.Triggers>
        </Style>
        
        <Style x:Key="ModernTextBox" TargetType="TextBox">
            <Setter Property="Background" Value="#1A1A1A"/>
            <Setter Property="Foreground" Value="White"/>
            <Setter Property="BorderBrush" Value="#333333"/>
            <Setter Property="CaretBrush" Value="#1DB954"/>
            <Setter Property="Padding" Value="10,8"/>
            <Setter Property="VerticalContentAlignment" Value="Center"/>
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="TextBox">
                        <Border x:Name="border" BorderBrush="{TemplateBinding BorderBrush}" BorderThickness="1" Background="{TemplateBinding Background}" CornerRadius="8">
                            <ScrollViewer x:Name="PART_ContentHost" Focusable="false" HorizontalScrollBarVisibility="Hidden" VerticalScrollBarVisibility="Hidden"/>
                        </Border>
                        <ControlTemplate.Triggers>
                            <Trigger Property="IsFocused" Value="True">
                                <Setter TargetName="border" Property="BorderBrush" Value="#1DB954"/>
                            </Trigger>
                        </ControlTemplate.Triggers>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
        </Style>
    </Window.Resources>

    <Grid Margin="30">
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
        </Grid.RowDefinitions>

        <StackPanel Grid.Row="0" Margin="0,0,0,20">
            <TextBlock Text="YouTube Audio" FontSize="32" Foreground="White" FontWeight="Bold" HorizontalAlignment="Center"/>
            <TextBlock Text="DOWNLOADER" FontSize="14" Foreground="#1DB954" FontWeight="Bold" LetterSpacing="5" HorizontalAlignment="Center" Margin="0,-5,0,0"/>
        </StackPanel>

        <StackPanel Grid.Row="1" VerticalAlignment="Center">
            <TextBlock Text="VIDEO URL" Foreground="#AAAAAA" FontSize="10" FontWeight="Bold" Margin="0,0,0,5"/>
            <TextBox x:Name="UrlTextBox" Style="{StaticResource ModernTextBox}" Margin="0,0,0,20"/>
            
            <TextBlock Text="SAVE TO" Foreground="#AAAAAA" FontSize="10" FontWeight="Bold" Margin="0,0,0,5"/>
            <Grid Margin="0,0,0,20">
                <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="Auto"/>
                </Grid.ColumnDefinitions>
                <TextBox x:Name="PathTextBox" Style="{StaticResource ModernTextBox}" IsReadOnly="True"/>
                <Button x:Name="BrowseButton" Grid.Column="1" Content="BROWSE" Style="{StaticResource ModernButton}" Margin="10,0,0,0" Width="100"/>
            </Grid>

            <Button x:Name="DownloadButton" Content="START DOWNLOAD" Style="{StaticResource ModernButton}" Height="50" FontSize="16" Margin="0,10,0,0"/>
        </StackPanel>

        <StackPanel Grid.Row="2" Margin="0,20,0,0">
            <ProgressBar x:Name="MainProgress" Height="6" Background="#222222" Foreground="#1DB954" BorderThickness="0" Margin="0,0,0,10">
                <ProgressBar.Resources>
                    <Style TargetType="Border">
                        <Setter Property="CornerRadius" Value="3"/>
                    </Style>
                </ProgressBar.Resources>
            </ProgressBar>
            <TextBlock x:Name="StatusText" Text="Ready to download" Foreground="#888888" HorizontalAlignment="Center" FontSize="12"/>
        </StackPanel>
    </Grid>
</Window>
"@

$reader = [XML.XmlReader]::Create([IO.StringReader] $xaml)
$window = [Windows.Markup.XamlReader]::Load($reader)

# --- Find Controls ---
$UrlTextBox = $window.FindName("UrlTextBox")
$PathTextBox = $window.FindName("PathTextBox")
$BrowseButton = $window.FindName("BrowseButton")
$DownloadButton = $window.FindName("DownloadButton")
$MainProgress = $window.FindName("MainProgress")
$StatusText = $window.FindName("StatusText")

$PathTextBox.Text = [Environment]::GetFolderPath("MyMusic")

# --- Helper Functions ---

function Update-UI {
    [System.Windows.Forms.Application]::DoEvents()
}

function Log($message, $percent = $null) {
    if ($null -ne $percent) { $MainProgress.Value = $percent }
    $StatusText.Text = $message
    Update-UI
}

function Download-File-With-Progress($url, $dest) {
    $client = New-Object System.Net.WebClient
    $eventAction = {
        param($sender, $e)
        Log "Downloading $($dest.Split('\')[-1])... $($e.ProgressPercentage)%" $e.ProgressPercentage
    }
    $client.Add_DownloadProgressChanged($eventAction)
    
    $task = $client.DownloadFileTaskAsync($url, $dest)
    while (!$task.IsCompleted) { Update-UI; Start-Sleep -Milliseconds 100 }
    
    if ($task.IsFaulted) { throw $task.Exception }
}

function Check-Dependencies {
    $needsReadyLog = $false
    
    if (!(Test-Path $YtDlpPath)) {
        Log "Downloading yt-dlp..." 0
        Download-File-With-Progress "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe" $YtDlpPath
        $needsReadyLog = $true
    }

    if (!(Test-Path $FfmpegPath)) {
        Log "Downloading FFmpeg..." 0
        $ffmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        $tempZip = Join-Path $env:TEMP "ffmpeg.zip"
        Download-File-With-Progress $ffmpegUrl $tempZip
        
        Log "Extracting FFmpeg..." 50
        $tempExt = Join-Path $env:TEMP "ffmpeg_ext"
        if (Test-Path $tempExt) { Remove-Item $tempExt -Recurse -Force }
        Expand-Archive -Path $tempZip -DestinationPath $tempExt -Force
        
        $ffmpegExeSource = Get-ChildItem -Path $tempExt -Filter "ffmpeg.exe" -Recurse | Select-Object -First 1
        Copy-Item $ffmpegExeSource.FullName $FfmpegPath -Force
        
        Remove-Item $tempZip -Force
        Remove-Item $tempExt -Recurse -Force
        $needsReadyLog = $true
    }
    
    if ($needsReadyLog) { Log "Ready to download" 0 }
}

# --- Event Handlers ---

$BrowseButton.Add_Click({
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.SelectedPath = $PathTextBox.Text
    $result = $dialog.ShowDialog()
    if ($result -eq [System.Windows.Forms.DialogResult]::OK -or $result -eq "OK") {
        $PathTextBox.Text = $dialog.SelectedPath
    }
})

$DownloadButton.Add_Click({
    $url = $UrlTextBox.Text.Trim()
    if ([string]::IsNullOrWhiteSpace($url)) {
        [System.Windows.MessageBox]::Show("Please enter a YouTube URL.")
        return
    }

    $outputPath = Join-Path $PathTextBox.Text "%(title)s.%(ext)s"
    
    $DownloadButton.IsEnabled = $false
    $BrowseButton.IsEnabled = $false
    $UrlTextBox.IsEnabled = $false

    try {
        Check-Dependencies

        Log "Fetching metadata..." 10
        
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $YtDlpPath
        # Added --newline to help with parsing progress output
        $startInfo.Arguments = "--extract-audio --audio-format mp3 --ffmpeg-location `"$FfmpegPath`" --newline -o `"$outputPath`" `"$url`""
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true

        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $startInfo
        $process.Start() | Out-Null

        while (!$process.HasExited) {
            $line = $process.StandardOutput.ReadLine()
            if ($line) {
                # Look for progress percentage like [download]  12.5% of 10.00MiB at ...
                if ($line -match '\[download\]\s+(\d+\.\d+)%') {
                    $percent = [double]$Matches[1]
                    Log "Downloading: $percent%" $percent
                } elseif ($line -match '\[ExtractAudio\]') {
                    Log "Converting to MP3..." 95
                }
            }
            Update-UI
            Start-Sleep -Milliseconds 50
        }

        if ($process.ExitCode -eq 0) {
            Log "Download Complete!" 100
            [System.Windows.MessageBox]::Show("Audio downloaded successfully!", "Success")
        } else {
            $errorMsg = $process.StandardError.ReadToEnd()
            Log "Error occurred." 0
            [System.Windows.MessageBox]::Show("An error occurred:`n$errorMsg", "Download Error")
        }
    } catch {
        Log "Fatal error." 0
        [System.Windows.MessageBox]::Show("Critical error: $($_.Exception.Message)")
    } finally {
        $DownloadButton.IsEnabled = $true
        $BrowseButton.IsEnabled = $true
        $UrlTextBox.IsEnabled = $true
        Log "Ready to download" 0
    }
})

# Launch App
$window.ShowDialog() | Out-Null
