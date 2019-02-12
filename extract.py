import re
import nltk
import sys


def verify_rounding_section_present(cur_page, next_page):
    # In the worst case, if cur_page contains only the "Rounding" word and the next_page contains the actual rounding section, both the pages will be POS tagged.
    # Not worrying about it for now
    rounding_section_present, continued_in_next_page = is_rounding_section_in_page("\n".join([cur_page, next_page]))
    if rounding_section_present and not continued_in_next_page: # These two pages have all the content
        return True
    return False


def is_rounding_section_in_page(page_content):

    # Case sensitive, not using regex because we are looking for an exact match
    _r = "Rounding" in page_content
    _del = "Delivery Amount" in page_content
    _ret = "Return Amount" in page_content
    
    # Regex to match currency and amount.
    # From https://en.wikipedia.org/wiki/ISO_4217 all currency notations are of 3 capital letters.
    amount = re.compile(r'[A-Z]{3}\s*\d+([,]\d+)*')
    amount_present = amount.search(page_content)

    if _r and _del and _ret and amount_present:
        return True, False # Rounding section is present in this page
    elif _r:
        # Rounding is present, but not the entire paragraph. Need to check the next page
        # In case this was just a word and not the section itself, verify_rounding_section_present takes care of this
        return True, True 
    else:
        return False, False


def chunk(tags):
    def parse_together_leaves(leaves):
		
        pass

    def parse_separate_leaves(leaves):
        pass

    grammar = ( 
                '''
                    TOGETHER: {<DT>?<NNP>{2}<.*>{0,10}<CC><.*>{0,10}<DT>?<NNP>{2}<.*>{0,5}?<VBN>(<RP>|<RB>)<.*>{0,2}(<RP>|<RB>)<.*>{0,10}<NNP>(<CD>(<,><NNP>)*)}
                    SEPARATE: {<DT>?<NNP>{2}<.*>{0,10}?<VBN>(<RP>|<RB>)<.*>{0,10}?<NNP>(<CD>(<,><NNP>)*)}  
                '''
            )
    chunk_regex_parser = nltk.RegexpParser(grammar)
    parsed_tree = chunk_regex_parser.parse(tags)
    subtree_matches = parsed_tree.subtrees(filter=lambda x: x.label() in ['TOGETHER', 'SEPARATE'])
    for match in subtree_matches:
        print (match.label(), match.leaves())
        # In case there are false positive matches for TOGETHER or SEPARATE, handle them by checking for Delivery and Return amount in particular
        words, tags = [], []
        for l in match.leaves():
            words.append(l[0])
            tags.append(l[1])
        if match.label() == 'TOGETHER':
            data_found = parse_together_leaves(match.leaves()) # Once the data is found, its safe to break from the loop
            if data_found:
                break
        else:
            parse_separate_leaves(match.leaves()) # Delivery and Return amounts are separate, so letting the loop run for all subtrees

def pos_tag(pages):
    page_contents = '\n'.join(pages)
    tags = nltk.pos_tag(nltk.word_tokenize(page_contents))    
    chunk(tags)


def read_pdf(pdf_file):
    from tika import parser
    
    try:
        file_content = parser.from_file(pdf_file)['content']
    except FileNotFoundError:
        sys.exit('File not found, please pass a valid path')

    pagewise_content = [page_content for page_content in file_content.split('\n\n\n\n') if len(page_content) > 0]
    
    num_pages = len(pagewise_content)
    print (num_pages)

    def update_pointers(dir_flag, fwd_ptr, back_ptr):
        if not dir_flag and fwd_ptr >= num_pages:
            # No need to change pointer direction as the forward pointer has reached file's end
            # It is guaranteed that forward pointer will reach file's end before backward pointer reaches the first page because we are starting at q3
            back_ptr -= 1
        else: # Forward pointer has not reached file's end. Continue search in both directions
            if dir_flag:
                fwd_ptr += 1
            else:
                back_ptr -= 1
            dir_flag = not dir_flag
        return dir_flag, fwd_ptr, back_ptr

    # from the 4 pdfs given, its noticeable that the rounding section is generally around the 3rd quartile
    q3 = (int)(0.75 * num_pages)
    backward_pointer = q3 - 1
    forward_pointer = q3
    read_direction_forward = True # If read direction forward is True, use forward pointer else use backward pointer
    
    while(forward_pointer < num_pages or backward_pointer >= 0):
        pointer = forward_pointer if read_direction_forward else backward_pointer # Search a page forward and backward around q3
        print ("Checking page", pointer)
        cur_page_content = pagewise_content[pointer] 
        rounding_section_present, continued_in_next_page = is_rounding_section_in_page(cur_page_content)
        if rounding_section_present: # If rounding section is found, POS tag page
            if continued_in_next_page: # In case rounding section is continued in next page
                # Make sure this indeed is the rounding section and not just the word "rounding"
                next_page_content = pagewise_content[pointer + 1] 
                if verify_rounding_section_present(cur_page_content, next_page_content):
                    pos_tag([cur_page_content, next_page_content])
                    break # Break the loop because the rounding section has been found
                else:
                    read_direction_forward, forward_pointer, backward_pointer = update_pointers(read_direction_forward, forward_pointer, backward_pointer)
            else:
                pos_tag([cur_page_content])
                break # Break the loop because the rounding section has been found
        else: # Continue search
            read_direction_forward, forward_pointer, backward_pointer = update_pointers(read_direction_forward, forward_pointer, backward_pointer)



if __name__ == '__main__':
    if len(sys.argv) >= 2:
        read_pdf(sys.argv[1])
    else:
        print ("Pass a PDF file to extract data from")
