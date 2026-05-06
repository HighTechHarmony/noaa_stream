#!/usr/bin/perl

use HTTP::Request;
use WWW::Curl::UserAgent;
use File::Copy qw(copy);
use FindBin;

# Load environment file (if NOAA_HOME not set in environment)
my $envfile = "$FindBin::Bin/.env";
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
my $home_path = $ENV{NOAA_HOME} || $FindBin::Bin;

my $ua = WWW::Curl::UserAgent->new(
    timeout         => 10000,
    connect_timeout => 1000,
    User-Agent => 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.89 Safari/537.36',
);
 
$ua->add_request(
	request    => HTTP::Request->new( GET => ($ENV{NOAA_AFD_URL} || 'https://forecast.weather.gov/product.php?site=BTV&issuedby=BTV&product=AFD&format=CI&version=1&glossary=1&highlight=off') ),
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

		if ($response_text=~/KEY\ MESSAGES\.\.\.(.*?)\&\&/s) {
			$synopsis="Synopsis for $product_date. ".$1;
#			print $synopsis;
#			`/usr/local/bin/swift \"$synopsis\"`;
			print "Updating synopsis cache\n";
			copy "$home_path/synopsis.txt","$home_path/synopsis.cache";
			print "Writing synopsis discussion\n";
			open (LSOUT,">$home_path/synopsis.txt");	
			print LSOUT $synopsis;
			close (LSOUT);

		}
		else {print "Unable to find KEY MESSAGES (Synopsis)\n";}




		if ($response_text=~/DISCUSSION\.\.\.(.*?)KEY\ MESSAGE\ 2/s) {
			$near_term="Near Term for $product_date. ".$1;
#			print $near_term;
#			`/usr/local/bin/swift \"$near_term\"`;
			print "Writing near term discussion\n";
			open (LSOUT,">$home_path/near_term.txt");	
			print LSOUT $near_term;
			close (LSOUT);

		}
		else {print "Unable to find KEY MESSAGE 1 (Near Term)\n";}



		if ($response_text=~/KEY MESSAGE 2.(.*?)KEY MESSAGE 3/s) {
			$short_term="Short Term for $product_date. ".$1;
#			print $short_term;
#			`/usr/local/bin/swift \"$short_term\"`;
			print "Writing short term discussion\n";
			open (LSOUT,">$home_path/short_term.txt");	
			print LSOUT $short_term;
			close (LSOUT);

		}
		else {print "Unable to find KEY MESSAGE 2 (SHORT TERM)\n";}



		if ($response_text=~/KEY MESSAGE 3.(.*?)\&\&/s) {
			$long_term="Long Term for $product_date. ".$1;
#			print $long_term;
			print "Writing long term discussion\n";
			open (LSOUT,">$home_path/long_term.txt");	
			print LSOUT $long_term;
			close (LSOUT);
		}
		else {print "Unable to find KEY MESSAGE 3 (LONG TERM)\n";}
		



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

