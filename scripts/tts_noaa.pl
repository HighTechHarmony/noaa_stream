#!/usr/bin/perl

use HTTP::Request;
use WWW::Curl::UserAgent;
use File::Copy qw(copy);
use FindBin;
use File::Basename qw(basename dirname);
use File::Path qw(make_path);
use lib $FindBin::Bin;
use ForecastSections qw(extract_key_messages map_forecast_sections);

# Load environment file (if NOAA_HOME not set in environment)
my $project_path = basename($FindBin::Bin) eq 'scripts' ? dirname($FindBin::Bin) : $FindBin::Bin;
my $envfile = "$project_path/.env";
if (!defined $ENV{NOAA_HOME} && -r $envfile) {
	if (open my $efh, '<', $envfile) {
		while (<$efh>) {
			chomp;
			next if $_ =~ /^\s*#/;
			next unless $_ =~ /=/;
			my ($k,$v) = split(/=/, $_, 2);
			$k =~ s/^\s+|\s+$//g;
			$v =~ s/^\s+|\s+$//g;
			$v =~ s/^"//; $v =~ s/"$//;
			$ENV{$k} = $v if defined $k && defined $v;
		}
		close $efh;
	}
}

# Prefer explicit environment variable, otherwise fall back to script dir
my $home_path = $ENV{NOAA_HOME} || $project_path;
my $forecast_text_dir = "$home_path/forecasts/text";
my $cache_dir = "$home_path/cache";
make_path($forecast_text_dir, $cache_dir);

eval { require TOML::Tiny; 1 } or die "TOML::Tiny is required to read config.toml: $@";
my $config_path = "$project_path/config.toml";
open my $config_fh, '<', $config_path or die "Cannot read $config_path: $!\n";
my $config_text = do { local $/; <$config_fh> };
close $config_fh;
my $config = eval { TOML::Tiny::from_toml($config_text) };
die "Cannot parse $config_path: $@" if $@ || ref $config ne 'HASH';
my $afd_url = ref $config->{noaa} eq 'HASH' ? $config->{noaa}{afd_url} : undef;
die "noaa.afd_url in $config_path must be an HTTP(S) URL\n"
	unless defined $afd_url && $afd_url =~ m{\Ahttps?://[^\s/?#]+(?:[/?#][^\s]*)?\z}i;

my $ua = WWW::Curl::UserAgent->new(
    timeout         => 10000,
    connect_timeout => 1000,
    User-Agent => 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.89 Safari/537.36',
);
 
$ua->add_request(
	request    => HTTP::Request->new( GET => $afd_url ),
    on_success => sub {
        my ( $request, $response ) = @_;
        if ($response->is_success) {
            #print $response->content;
		$response_text=$response->content;
		$response_text=~s|<.+?>||g;	# Strip HTML

		if ($response_text=~/(\d\d\d+ \wM.*)/) {
                        $product_date=$1;
#			$product_date=~s/ AM / A M /g;
#			$product_date=~s/ PM / P M /g;
			$product_date=~s/ EST / Eastern Standard Time, /g;
			$product_date=~s/ EDT / Eastern Daylight Time, /g;

                        print "Retreived NOAA product with date $product_date\n";
                }
                else {print "Unable to find PRODUCT DATE\n";}


		#print $response_text;

		$response_text=~s/\n/ /g;  #Strip out newlines
		$response_text=~s/\r//g;   #Strip carriage returns
		$response_text=~s/\`//g;   #Strip out backquotes
#		$response_text=~s/ \///g;   #Strip out some slashes
#		$response_text=~s/\/ //g;   #Strip out some slashes

		# Expand some common abbreviations that help Cepstral a little
		sub load_abbreviations {
			my ($file) = @_;
			my %h;
			return %h unless defined $file && -r $file;
			open my $fh, '<', $file or return %h;
			while (<$fh>) {
				chomp;
				s/^\s+|\s+$//g;
				next if $_ eq '' or $_ =~ /^\s*#/;
				my ($a,$b) = split(/\s*,\s*/, $_, 2);
				next unless defined $a and defined $b;
				$a =~ s/^"//; $a =~ s/"$//;
				$b =~ s/^"//; $b =~ s/"$//;
				$a =~ s/^\s+|\s+$//g;
				$b =~ s/^\s+|\s+$//g;
				$h{lc $a} = $b;
			}
			close $fh;
			return %h;
		}

		my %abbrev = load_abbreviations("$home_path/abbreviations.csv");
		# Diagnostic: ensure common keys loaded
		warn "Abbrev 'wed' present\n" if exists $abbrev{lc 'Wed'};

		# Replacement that is case-insensitive but preserves capitalization
		sub _preserve_case {
			my ($orig, $replacement) = @_;
			return uc($replacement)   if $orig =~ /^\p{Lu}+$/;
			return lc($replacement)   if $orig =~ /^\p{Ll}+$/;
			return ucfirst(lc($replacement)) if $orig =~ /^\p{Lu}\p{Ll}+$/;
			return $replacement;
		}

		for my $k (sort { length $b <=> length $a } keys %abbrev) {
			my $v = $abbrev{$k};
			my $re = qr/(\b\Q$k\E\b)/i;
			my $count = 0;
			$response_text =~ s/$re/ do { $count++; _preserve_case($1, $v) } /ge;
			warn "Replaced $count occurrences of '$k'\n" if $count;
			# Also apply abbreviation replacements to the extracted product date
			if (defined $product_date) {
				my $count_pd = 0;
				$product_date =~ s/$re/ do { $count_pd++; _preserve_case($1, $v) } /ge;
				warn "Replaced $count_pd occurrences of '$k' in product_date\n" if $count_pd;
			}
		}

		# Keep a few fixed replacements helpful to TTS
		$response_text=~s/\b[Ss]fc\b/surface/g;
		$response_text=~s/\bpres\b/pressure/g;
		$response_text=~s/\baftn\b/afternoon/g;
		$response_text=~s/\bobs\b/observation/g;
		$response_text=~s/ AM / A M /g;
		$response_text=~s/ PM / P M /g;
		$response_text=~s/ EST / Eastern Standard Time /g;
		$response_text=~s/ EDT / Eastern Daylight Time /g;


#		print $response_text;
#die;

		my $messages = extract_key_messages($response_text);
		my $sections = map_forecast_sections($messages);
		die "Unable to find numbered KEY MESSAGE sections\n" unless keys %$sections;

		print "Updating synopsis cache\n";
		copy "$forecast_text_dir/synopsis.txt", "$cache_dir/synopsis.cache";

		my %section_labels = (
			synopsis   => 'Synopsis',
			near_term  => 'Near Term',
			short_term => 'Short Term',
			long_term  => 'Long Term',
		);
		for my $section (qw(synopsis near_term short_term long_term)) {
			my $text = "$section_labels{$section} for $product_date. $sections->{$section}";
			my $path = "$forecast_text_dir/$section.txt";
			print "Writing $section discussion\n";
			open my $output, '>', $path or die "Cannot write $path: $!\n";
			print {$output} $text;
			close $output or die "Cannot close $path: $!\n";
		}
		



        }
        else {
            die $response->status_line;
        }
    },
    on_failure => sub {
        my ( $request, $error_msg, $error_desc ) = @_;
        die "$error_msg: $error_desc";
    },
);
$ua->perform;

