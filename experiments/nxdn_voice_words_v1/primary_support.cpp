/*
 *	Copyright (C) 2009,2014,2015,2016,2021,2022,2023,2025 Jonathan Naylor, G4KLX
 *
 *	This program is free software; you can redistribute it and/or modify
 *	it under the terms of the GNU General Public License as published by
 *	the Free Software Foundation; version 2 of the License.
 *
 *	This program is distributed in the hope that it will be useful,
 *	but WITHOUT ANY WARRANTY; without even the implied warranty of
 *	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *	GNU General Public License for more details.
 */

// Exact function body from MMDVM-Host Utils.cpp lines 155-165, commit
// 590c531391dfd3146073afbc3956f70d42c62a46. The unmodified Golay translation
// unit references this utility in its unused decoder method. Providing the
// actual utility avoids linking host logging/network dependencies; neither
// this wrapper nor the oracle calls an upstream decoder.
#include "Utils.h"

unsigned int CUtils::countBits(unsigned int v)
{
	unsigned int count = 0U;

	while (v != 0U) {
		v &= v - 1U;
		count++;
	}

	return count;
}
