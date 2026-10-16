package ForecastSections;

use strict;
use warnings;
use Exporter qw(import);

our @EXPORT_OK = qw(extract_key_messages map_forecast_sections);

sub extract_key_messages {
	my ($response_text) = @_;
	return {} unless defined $response_text;

	my ($discussion) = $response_text =~ /\bDISCUSSION\.\.\.(.*?)(?:&&|\z)/is;
	return {} unless defined $discussion;

	my %messages;
	while ($discussion =~ /\bKEY\s+MESSAGE\s+(\d+)\s*[:.]\s*(.*?)(?=\bKEY\s+MESSAGE\s+\d+\s*[:.]|\z)/gis) {
		my ($number, $body) = ($1, $2);
		$body =~ s/^\s+|\s+$//g;
		$messages{$number} = $body if length $body;
	}

	return \%messages;
}

sub map_forecast_sections {
	my ($messages) = @_;
	return {} unless ref $messages eq 'HASH';

	my @numbers = sort { $a <=> $b } grep { defined $messages->{$_} && length $messages->{$_} } keys %$messages;
	return {} unless @numbers;

	my $last = $#numbers;
	my $near_index = $last > 0 ? 1 : 0;
	my $short_index = $last > 0 ? $last - 1 : 0;

	return {
		synopsis   => $messages->{$numbers[0]},
		near_term  => $messages->{$numbers[$near_index]},
		short_term => $messages->{$numbers[$short_index]},
		long_term  => $messages->{$numbers[$last]},
	};
}

1;